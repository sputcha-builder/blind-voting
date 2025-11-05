from flask import Flask, render_template, request, jsonify, redirect
import os
from datetime import datetime
from anthropic import Anthropic

# Import storage layer - automatically uses JSON or PostgreSQL based on DATABASE_URL
from storage import (
    load_votes, save_votes, save_vote,
    load_config, save_config,
    load_roles, save_roles, save_role,
    get_role_by_id, delete_role as delete_role_storage,
    init_db, USE_DATABASE
)

app = Flask(__name__)

# Initialize Anthropic Claude client (API key from environment variable)
claude_client = None
if os.environ.get('ANTHROPIC_API_KEY'):
    claude_client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))

# Detect if running in production (Render sets PORT environment variable)
IS_PRODUCTION = 'RENDER' in os.environ or os.environ.get('PORT') == '10000'

# Initialize database if using PostgreSQL
if USE_DATABASE:
    try:
        init_db()
        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        raise

# Force HTTPS in production
@app.before_request
def before_request():
    """Redirect HTTP to HTTPS in production"""
    if IS_PRODUCTION:
        # Check if request was made over HTTP (via X-Forwarded-Proto header from proxy)
        if request.headers.get('X-Forwarded-Proto', 'http') != 'https':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # Add HSTS header in production
    if IS_PRODUCTION:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# Global error handlers to return JSON instead of HTML for API endpoints
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors - return JSON for API endpoints, HTML for pages"""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Endpoint not found'}), 404
    return render_template('vote.html'), 404  # Redirect to voting page for non-API 404s

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors - return JSON for API endpoints"""
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': f'Internal server error: {str(error)}'}), 500
    return f"Internal server error: {str(error)}", 500

@app.errorhandler(Exception)
def handle_exception(error):
    """Global exception handler - return JSON for API endpoints"""
    import traceback
    error_details = str(error)

    # Log the full traceback for debugging
    if not IS_PRODUCTION:
        print(f"\n{'='*60}\nUNHANDLED EXCEPTION:\n{traceback.format_exc()}{'='*60}\n")

    # Return JSON for API endpoints
    if request.path.startswith('/api/'):
        # Check for common database errors
        if 'UUID' in error_details or 'uuid' in error_details.lower():
            return jsonify({'success': False, 'message': 'Invalid ID format. Please try again or refresh the page.'}), 400
        elif 'database' in error_details.lower() or 'connection' in error_details.lower():
            return jsonify({'success': False, 'message': 'Database connection error. Please try again in a moment.'}), 500
        else:
            return jsonify({'success': False, 'message': f'An error occurred: {error_details}'}), 500

    # For non-API endpoints, return simple error page
    return f"An error occurred: {error_details}", 500

def migrate_config_to_roles():
    """Migrate existing config.json to roles format (one-time migration)"""
    # Check if roles already exist
    roles_data = load_roles()
    if len(roles_data.get('roles', [])) > 0:
        return  # Already migrated

    # Load existing config
    config = load_config()

    # If config is not configured, create empty roles structure
    if not config.get('is_configured'):
        save_roles({'roles': []})
        return

    # Create first role from existing config
    import uuid
    role_id = str(uuid.uuid4())

    role = {
        'id': role_id,
        'position': config.get('position', ''),
        'candidates': config.get('candidates', []),
        'allowed_emails': config.get('allowed_emails', []),
        'status': 'active',
        'created_at': datetime.now().isoformat()
    }

    save_roles({'roles': [role]})

    # Update existing votes to include role_id
    votes_data = load_votes()
    for vote in votes_data['votes']:
        if 'role_id' not in vote:
            vote['role_id'] = role_id
    save_votes(votes_data)

def get_total_voters():
    """Get total number of voters from config"""
    config = load_config()
    if config['is_configured']:
        # Count non-empty emails
        return len([email for email in config['allowed_emails'] if email.strip()])
    return 0

def get_total_candidates():
    """Get total number of candidates from config"""
    config = load_config()
    return len(config.get('candidates', []))

def get_voter_progress(voter_email):
    """Get which candidates a voter has voted on"""
    votes_data = load_votes()
    voted_candidate_ids = []
    for vote in votes_data['votes']:
        if vote['voter'].lower() == voter_email.lower():
            voted_candidate_ids.append(vote['candidate_id'])
    return voted_candidate_ids

def is_voting_complete():
    """Check if all voters have voted on all candidates"""
    config = load_config()
    votes_data = load_votes()

    total_voters = get_total_voters()
    total_candidates = get_total_candidates()

    if total_voters == 0 or total_candidates == 0:
        return False

    expected_total_votes = total_voters * total_candidates
    actual_total_votes = len(votes_data['votes'])

    return actual_total_votes >= expected_total_votes

@app.route('/')
def index():
    """Redirect to voting page"""
    return render_template('vote.html')

@app.route('/vote')
def vote_page():
    """Display voting page"""
    return render_template('vote.html')

@app.route('/api/vote', methods=['POST'])
def submit_vote():
    """Submit a vote for a candidate"""
    data = request.json
    voter_email = data.get('voter_email', '').strip().lower()
    candidate_id = data.get('candidate_id', '')
    choice = data.get('choice', '')
    feedback = data.get('feedback', '').strip()
    role_id = data.get('role_id', '')  # Optional for multi-role support

    # If role_id is provided, use new multi-role system
    if role_id:
        role = get_role_by_id(role_id)
        if not role:
            return jsonify({'success': False, 'message': 'Role not found'}), 404

        # Validate email
        if not voter_email:
            return jsonify({'success': False, 'message': 'Please enter your email'}), 400

        # Check if email is in allowed list for this role
        allowed_emails = [email.strip().lower() for email in role.get('allowed_emails', []) if email.strip()]
        if voter_email not in allowed_emails:
            return jsonify({'success': False, 'message': 'Your email is not authorized to vote for this role'}), 403

        # Validate candidate
        if not candidate_id:
            return jsonify({'success': False, 'message': 'Candidate ID is required'}), 400

        candidate = next((c for c in role.get('candidates', []) if c['id'] == candidate_id), None)
        if not candidate:
            return jsonify({'success': False, 'message': 'Invalid candidate'}), 400

        # Validate choice
        if choice not in ['Inclined', 'Not Inclined']:
            return jsonify({'success': False, 'message': 'Invalid choice'}), 400

        # Validate feedback
        if not feedback:
            return jsonify({'success': False, 'message': 'Feedback is required'}), 400

        # Load existing votes
        votes_data = load_votes()

        # Check if voter already voted for this candidate in this role - if so, update it
        existing_vote_index = None
        for i, vote in enumerate(votes_data['votes']):
            if (vote['voter'].lower() == voter_email and
                vote['candidate_id'] == candidate_id and
                vote.get('role_id') == role_id):
                existing_vote_index = i
                break

        vote_record = {
            'voter': voter_email,
            'candidate_id': candidate_id,
            'candidate_name': candidate['name'],
            'role_id': role_id,
            'role_position': role['position'],
            'choice': choice,
            'feedback': feedback,
            'timestamp': datetime.now().isoformat()
        }

        if existing_vote_index is not None:
            # Update existing vote
            votes_data['votes'][existing_vote_index] = vote_record
            message = f'Vote updated for {candidate["name"]} ({role["position"]})!'
        else:
            # Add new vote
            votes_data['votes'].append(vote_record)
            message = f'Vote recorded for {candidate["name"]} ({role["position"]})!'

        # Save votes
        save_votes(votes_data)

        # Count progress for this role
        role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role_id and v['voter'].lower() == voter_email]
        total_candidates = len(role.get('candidates', []))

        return jsonify({
            'success': True,
            'message': message,
            'votes_submitted': len(role_votes),
            'total_candidates': total_candidates
        })

    # Legacy path: Use old config.json system if no role_id provided
    # Load configuration
    config = load_config()

    # Check if system is configured
    if not config['is_configured']:
        return jsonify({'success': False, 'message': 'Voting is not configured yet. Please contact the admin.'}), 400

    # Validate email
    if not voter_email:
        return jsonify({'success': False, 'message': 'Please enter your email'}), 400

    # Check if email is in allowed list
    allowed_emails = [email.strip().lower() for email in config['allowed_emails'] if email.strip()]
    if voter_email not in allowed_emails:
        return jsonify({'success': False, 'message': 'Your email is not authorized to vote'}), 403

    # Validate candidate
    if not candidate_id:
        return jsonify({'success': False, 'message': 'Candidate ID is required'}), 400

    candidate = next((c for c in config['candidates'] if c['id'] == candidate_id), None)
    if not candidate:
        return jsonify({'success': False, 'message': 'Invalid candidate'}), 400

    # Validate choice
    if choice not in ['Inclined', 'Not Inclined']:
        return jsonify({'success': False, 'message': 'Invalid choice'}), 400

    # Validate feedback
    if not feedback:
        return jsonify({'success': False, 'message': 'Feedback is required'}), 400

    # Load existing votes
    votes_data = load_votes()

    # Check if voter already voted for this candidate - if so, update it
    existing_vote_index = None
    for i, vote in enumerate(votes_data['votes']):
        if vote['voter'].lower() == voter_email and vote['candidate_id'] == candidate_id:
            existing_vote_index = i
            break

    vote_record = {
        'voter': voter_email,
        'candidate_id': candidate_id,
        'candidate_name': candidate['name'],
        'choice': choice,
        'feedback': feedback,
        'timestamp': datetime.now().isoformat()
    }

    if existing_vote_index is not None:
        # Update existing vote
        votes_data['votes'][existing_vote_index] = vote_record
        message = f'Vote updated for {candidate["name"]}!'
    else:
        # Add new vote
        votes_data['votes'].append(vote_record)
        message = f'Vote recorded for {candidate["name"]}!'

    # Save votes
    save_votes(votes_data)

    # Check progress
    voter_progress = get_voter_progress(voter_email)
    total_candidates = get_total_candidates()

    return jsonify({
        'success': True,
        'message': message,
        'votes_submitted': len(voter_progress),
        'total_candidates': total_candidates
    })

@app.route('/api/voter/progress', methods=['POST'])
def get_voter_progress_api():
    """Get voter's progress (which candidates they've voted on)"""
    data = request.json
    voter_email = data.get('voter_email', '').strip().lower()

    if not voter_email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    config = load_config()
    votes_data = load_votes()

    # Get all candidates
    candidates = config.get('candidates', [])

    # Get voter's votes
    voter_votes = {}
    for vote in votes_data['votes']:
        if vote['voter'].lower() == voter_email:
            voter_votes[vote['candidate_id']] = {
                'choice': vote['choice'],
                'feedback': vote['feedback'],
                'timestamp': vote['timestamp']
            }

    # Build response with candidate status
    candidate_status = []
    for candidate in candidates:
        vote_info = voter_votes.get(candidate['id'])
        candidate_status.append({
            'id': candidate['id'],
            'name': candidate['name'],
            'voted': vote_info is not None,
            'vote': vote_info if vote_info else None
        })

    return jsonify({
        'success': True,
        'candidates': candidate_status,
        'votes_submitted': len(voter_votes),
        'total_candidates': len(candidates)
    })

@app.route('/api/voter/role-progress', methods=['POST'])
def get_voter_role_progress_api():
    """Get voter's progress for a specific role (which candidates they've voted on)"""
    data = request.json
    voter_email = data.get('voter_email', '').strip().lower()
    role_id = data.get('role_id', '')

    if not voter_email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    if not role_id:
        return jsonify({'success': False, 'message': 'Role ID is required'}), 400

    role = get_role_by_id(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    votes_data = load_votes()

    # Get all candidates for this role
    candidates = role.get('candidates', [])

    # Get voter's votes for this role
    voter_votes = {}
    for vote in votes_data['votes']:
        if vote['voter'].lower() == voter_email and vote.get('role_id') == role_id:
            voter_votes[vote['candidate_id']] = {
                'choice': vote['choice'],
                'feedback': vote['feedback'],
                'timestamp': vote['timestamp']
            }

    # Build response with candidate status
    candidate_status = []
    for candidate in candidates:
        vote_info = voter_votes.get(candidate['id'])
        candidate_status.append({
            'id': candidate['id'],
            'name': candidate['name'],
            'voted': vote_info is not None,
            'vote': vote_info if vote_info else None
        })

    return jsonify({
        'success': True,
        'candidates': candidate_status,
        'votes_submitted': len(voter_votes),
        'total_candidates': len(candidates)
    })

@app.route('/results')
def results_page():
    """Display results page"""
    return render_template('results.html')

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get voting results (only if all voters have voted on all candidates)"""
    config = load_config()
    votes_data = load_votes()

    total_voters = get_total_voters()
    total_candidates = get_total_candidates()
    total_votes = len(votes_data['votes'])
    expected_votes = total_voters * total_candidates

    # Check if voting is complete
    if not is_voting_complete():
        return jsonify({
            'complete': False,
            'votes_received': total_votes,
            'votes_needed': expected_votes,
            'message': f'Waiting for {expected_votes - total_votes} more vote(s)',
            'position': config.get('position', ''),
            'is_configured': config.get('is_configured', False),
            'total_voters': total_voters,
            'total_candidates': total_candidates
        })

    # Build results for each candidate
    candidates_results = []
    for candidate in config.get('candidates', []):
        candidate_votes = [v for v in votes_data['votes'] if v['candidate_id'] == candidate['id']]

        inclined = sum(1 for v in candidate_votes if v['choice'] == 'Inclined')
        not_inclined = sum(1 for v in candidate_votes if v['choice'] == 'Not Inclined')

        candidates_results.append({
            'id': candidate['id'],
            'name': candidate['name'],
            'total_votes': len(candidate_votes),
            'inclined': inclined,
            'not_inclined': not_inclined,
            'votes': candidate_votes
        })

    return jsonify({
        'complete': True,
        'position': config.get('position', ''),
        'total_voters': total_voters,
        'total_candidates': total_candidates,
        'candidates': candidates_results,
        'is_configured': config.get('is_configured', False)
    })

@app.route('/api/results/<role_id>', methods=['GET'])
def get_role_results(role_id):
    """Get voting results for a specific role (only if all voters have voted on all candidates)"""
    role = get_role_by_id(role_id)

    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    votes_data = load_votes()
    role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role_id]

    total_voters = len(role.get('allowed_emails', []))
    total_candidates = len(role.get('candidates', []))
    expected_votes = total_voters * total_candidates

    # Check if voting is complete for this role
    if len(role_votes) < expected_votes:
        return jsonify({
            'complete': False,
            'votes_received': len(role_votes),
            'votes_needed': expected_votes,
            'message': f'Waiting for {expected_votes - len(role_votes)} more vote(s)',
            'position': role.get('position', ''),
            'total_voters': total_voters,
            'total_candidates': total_candidates,
            'role_id': role_id
        })

    # Build results for each candidate in this role
    candidates_results = []
    for candidate in role.get('candidates', []):
        candidate_votes = [v for v in role_votes if v['candidate_id'] == candidate['id']]

        inclined = sum(1 for v in candidate_votes if v['choice'] == 'Inclined')
        not_inclined = sum(1 for v in candidate_votes if v['choice'] == 'Not Inclined')

        candidates_results.append({
            'id': candidate['id'],
            'name': candidate['name'],
            'total_votes': len(candidate_votes),
            'inclined': inclined,
            'not_inclined': not_inclined,
            'votes': candidate_votes
        })

    return jsonify({
        'complete': True,
        'position': role.get('position', ''),
        'total_voters': total_voters,
        'total_candidates': total_candidates,
        'candidates': candidates_results,
        'role_id': role_id,
        'status': role.get('status', 'active')
    })

@app.route('/admin')
def admin_page():
    """Admin page for managing votes"""
    return render_template('admin.html')

@app.route('/api/reset', methods=['POST'])
def reset_votes():
    """Reset all votes and configuration (admin only)"""
    save_votes({'votes': []})
    save_config({
        'position': '',
        'candidates': [],
        'allowed_emails': [],
        'is_configured': False
    })
    return jsonify({'success': True, 'message': 'All votes and configuration have been reset'})

@app.route('/api/summarize', methods=['POST'])
def summarize_feedback():
    """Summarize raw interview notes using Claude AI"""
    if not claude_client:
        return jsonify({
            'success': False,
            'message': 'AI summarization not configured. Please set ANTHROPIC_API_KEY environment variable.'
        }), 400

    data = request.json
    raw_notes = data.get('notes', '').strip()
    choice = data.get('choice', '')  # 'Inclined' or 'Not Inclined'

    if not raw_notes:
        return jsonify({'success': False, 'message': 'Please provide notes to summarize'}), 400

    try:
        # Create prompt based on voting choice
        if choice == 'Inclined':
            user_prompt = f"""Please summarize these interview notes into a concise, well-structured format (max 250 words, about half an A4 page).

Format the output as:
**Summary:**
[Brief 2-3 sentence overview]

**Strengths:**
- [Bullet point 1]
- [Bullet point 2]
- [etc]

**Watchouts:**
- [Bullet point 1]
- [Bullet point 2]
- [etc]

Be professional, specific, and actionable.

Raw interview notes:
{raw_notes}"""
        else:  # Not Inclined
            user_prompt = f"""Please summarize these interview notes into a concise, well-structured format (max 250 words, about half an A4 page).

Format the output as:
**Summary:**
[Brief 2-3 sentence overview]

**Flags/Concerns:**
- [Bullet point 1]
- [Bullet point 2]
- [etc]

**Reasons Not to Hire:**
- [Bullet point 1]
- [Bullet point 2]
- [etc]

Be professional, specific, and actionable.

Raw interview notes:
{raw_notes}"""

        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",  # Fast and economical
            max_tokens=500,
            temperature=0.3,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        summary = response.content[0].text.strip()

        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error generating summary: {str(e)}'
        }), 500

@app.route('/api/aggregate-summary/<role_id>/<candidate_id>', methods=['POST'])
def generate_aggregate_summary(role_id, candidate_id):
    """Generate an aggregate summary of all voter feedback for a candidate"""
    if not claude_client:
        return jsonify({
            'success': False,
            'message': 'AI summarization not configured.'
        }), 400

    role = get_role_by_id(role_id)
    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    candidate = next((c for c in role.get('candidates', []) if c['id'] == candidate_id), None)
    if not candidate:
        return jsonify({'success': False, 'message': 'Candidate not found'}), 404

    votes_data = load_votes()
    candidate_votes = [v for v in votes_data['votes']
                      if v.get('role_id') == role_id and v['candidate_id'] == candidate_id]

    if not candidate_votes:
        return jsonify({'success': False, 'message': 'No votes found for this candidate'}), 404

    try:
        # Build combined feedback text
        feedback_text = f"Position: {role['position']}\nCandidate: {candidate['name']}\n\n"

        inclined_count = sum(1 for v in candidate_votes if v['choice'] == 'Inclined')
        not_inclined_count = sum(1 for v in candidate_votes if v['choice'] == 'Not Inclined')

        feedback_text += f"Vote Summary: {inclined_count} Inclined, {not_inclined_count} Not Inclined\n\n"
        feedback_text += "Individual Voter Feedback:\n\n"

        for i, vote in enumerate(candidate_votes, 1):
            feedback_text += f"Voter {i} ({vote['choice']}):\n{vote.get('feedback', 'No feedback provided')}\n\n"

        user_prompt = f"""You are reviewing interview feedback for a candidate. Below is the combined feedback from all interviewers.

Please create a concise executive summary (max 300 words) that synthesizes all feedback and provides a clear recommendation.

Format the output as:
**Executive Summary:**
[2-3 sentence overview of the candidate's performance and vote breakdown]

**Key Strengths:**
- [Synthesized strengths mentioned by multiple voters]
- [Additional strengths]

**Areas of Concern:**
- [Synthesized concerns/watchouts from multiple voters]
- [Additional concerns]

**Recommendation:**
[Based on the vote distribution and feedback, provide a clear hiring recommendation]

Be balanced, objective, and actionable. Highlight patterns across multiple voters.

{feedback_text}"""

        response = claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=700,
            temperature=0.3,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        summary = response.content[0].text.strip()

        return jsonify({
            'success': True,
            'summary': summary
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error generating summary: {str(e)}'
        }), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get current voting status"""
    config = load_config()
    votes_data = load_votes()
    total_voters = get_total_voters()
    total_candidates = get_total_candidates()

    return jsonify({
        'total_votes': len(votes_data['votes']),
        'votes_needed': total_voters * total_candidates if config.get('is_configured') else 0,
        'is_configured': config.get('is_configured', False),
        'candidates': config.get('candidates', []),
        'position': config.get('position', ''),
        'voting_locked': len(votes_data['votes']) > 0,
        'total_voters': total_voters,
        'total_candidates': total_candidates
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = load_config()
    votes_data = load_votes()

    return jsonify({
        'position': config.get('position', ''),
        'candidates': config.get('candidates', []),
        'allowed_emails': config.get('allowed_emails', []),
        'is_configured': config.get('is_configured', False),
        'voting_locked': len(votes_data['votes']) > 0
    })

@app.route('/api/config', methods=['POST'])
def save_configuration():
    """Save voting configuration - allows adding candidates even after voting starts"""
    data = request.json

    # Load existing config and votes
    existing_config = load_config()
    votes_data = load_votes()
    has_votes = len(votes_data['votes']) > 0

    position = data.get('position', '').strip()
    candidates = data.get('candidates', [])
    allowed_emails = data.get('allowed_emails', [])

    # Validate inputs
    if not position:
        return jsonify({'success': False, 'message': 'Position is required'}), 400

    # Validate candidates
    if not candidates or len(candidates) == 0:
        return jsonify({'success': False, 'message': 'At least one candidate is required'}), 400

    # Build valid candidates list
    # If votes exist, preserve existing candidate IDs and only allow adding new ones
    valid_candidates = []
    existing_candidates = {c['id']: c for c in existing_config.get('candidates', [])}

    # Get the highest existing candidate ID
    max_id = 0
    for existing_id in existing_candidates.keys():
        try:
            max_id = max(max_id, int(existing_id))
        except:
            pass

    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate_id = candidate.get('id')
            name = candidate.get('name', '').strip()
        else:
            candidate_id = None
            name = str(candidate).strip()

        if not name:
            continue

        # If this is an existing candidate (has ID), preserve it
        if candidate_id and candidate_id in existing_candidates:
            valid_candidates.append({
                'id': candidate_id,
                'name': name
            })
        else:
            # New candidate - assign next ID
            max_id += 1
            valid_candidates.append({
                'id': str(max_id),
                'name': name
            })

    if len(valid_candidates) == 0:
        return jsonify({'success': False, 'message': 'At least one candidate is required'}), 400

    # If votes exist, check that we're not removing candidates with votes
    if has_votes:
        voted_candidate_ids = set(vote['candidate_id'] for vote in votes_data['votes'])
        new_candidate_ids = set(c['id'] for c in valid_candidates)
        removed_candidates = voted_candidate_ids - new_candidate_ids

        if removed_candidates:
            removed_names = [existing_candidates[cid]['name'] for cid in removed_candidates if cid in existing_candidates]
            return jsonify({
                'success': False,
                'message': f'Cannot remove candidates with existing votes: {", ".join(removed_names)}'
            }), 400

    # Filter out empty emails and validate
    valid_emails = []
    for email in allowed_emails:
        email = email.strip()
        if email:
            # Basic email validation
            if '@' not in email or '.' not in email:
                return jsonify({'success': False, 'message': f'Invalid email format: {email}'}), 400
            valid_emails.append(email)

    if len(valid_emails) == 0:
        return jsonify({'success': False, 'message': 'At least one voter email is required'}), 400

    if len(valid_emails) > 5:
        return jsonify({'success': False, 'message': 'Maximum 5 voters allowed'}), 400

    # Save configuration
    config_data = {
        'position': position,
        'candidates': valid_candidates,
        'allowed_emails': valid_emails,
        'is_configured': True
    }
    save_config(config_data)

    return jsonify({
        'success': True,
        'message': f'Configuration saved! {len(valid_candidates)} candidate(s) and {len(valid_emails)} voter(s) configured.'
    })

@app.route('/api/roles', methods=['POST'])
def create_role():
    """Create a new role/position"""
    try:
        data = request.json

        position = data.get('position', '').strip()
        candidates = data.get('candidates', [])
        allowed_emails = data.get('allowed_emails', [])
        status = data.get('status', 'active')
    except Exception as e:
        return jsonify({'success': False, 'message': f'Invalid request data: {str(e)}'}), 400

    # Validate position
    if not position:
        return jsonify({'success': False, 'message': 'Position is required'}), 400

    # Validate and build candidates list
    valid_candidates = []
    candidate_id = 1
    for candidate in candidates:
        if isinstance(candidate, dict):
            name = candidate.get('name', '').strip()
        else:
            name = str(candidate).strip()

        if name:
            valid_candidates.append({
                'id': str(candidate_id),
                'name': name
            })
            candidate_id += 1

    if len(valid_candidates) == 0:
        return jsonify({'success': False, 'message': 'At least one candidate is required'}), 400

    # Validate emails
    valid_emails = []
    for email in allowed_emails:
        email = email.strip()
        if email:
            if '@' not in email or '.' not in email:
                return jsonify({'success': False, 'message': f'Invalid email format: {email}'}), 400
            valid_emails.append(email)

    if len(valid_emails) == 0:
        return jsonify({'success': False, 'message': 'At least one voter email is required'}), 400

    if len(valid_emails) > 5:
        return jsonify({'success': False, 'message': 'Maximum 5 voters allowed'}), 400

    # Validate status
    if status not in ['active', 'fulfilled', 'expired']:
        status = 'active'

    # Create new role
    try:
        import uuid
        role_id = str(uuid.uuid4())

        role = {
            'id': role_id,
            'position': position,
            'candidates': valid_candidates,
            'allowed_emails': valid_emails,
            'status': status,
            'created_at': datetime.now().isoformat()
        }

        # Load existing roles and add new one
        roles_data = load_roles()
        roles_data['roles'].append(role)
        save_roles(roles_data)

        return jsonify({
            'success': True,
            'message': f'Role "{position}" created successfully',
            'role': role
        })
    except Exception as e:
        import traceback
        print(f"Error creating role: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error creating role: {str(e)}'}), 500

@app.route('/api/roles', methods=['GET'])
def list_roles():
    """List all roles with optional status filter"""
    try:
        status_filter = request.args.get('status')  # active, fulfilled, expired

        roles_data = load_roles()
        roles = roles_data['roles']

        # Filter by status if provided
        if status_filter:
            roles = [r for r in roles if r.get('status') == status_filter]

        # Add vote counts to each role
        votes_data = load_votes()
        for role in roles:
            role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role['id']]
            total_voters = len(role.get('allowed_emails', []))
            total_candidates = len(role.get('candidates', []))
            expected_votes = total_voters * total_candidates

            role['vote_stats'] = {
                'total_votes': len(role_votes),
                'expected_votes': expected_votes,
                'is_complete': len(role_votes) >= expected_votes if expected_votes > 0 else False
            }

        return jsonify({
            'success': True,
            'roles': roles,
            'total': len(roles)
        })
    except Exception as e:
        import traceback
        print(f"Error listing roles: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error loading roles: {str(e)}'}), 500

@app.route('/api/roles/<role_id>', methods=['GET'])
def get_role(role_id):
    """Get a specific role by ID"""
    role = get_role_by_id(role_id)

    if not role:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    # Add vote stats
    votes_data = load_votes()
    role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role_id]
    total_voters = len(role.get('allowed_emails', []))
    total_candidates = len(role.get('candidates', []))
    expected_votes = total_voters * total_candidates

    role['vote_stats'] = {
        'total_votes': len(role_votes),
        'expected_votes': expected_votes,
        'is_complete': len(role_votes) >= expected_votes if expected_votes > 0 else False
    }

    return jsonify({
        'success': True,
        'role': role
    })

@app.route('/api/roles/<role_id>', methods=['PUT'])
def update_role(role_id):
    """Update a role (status, add candidates, add voters)"""
    try:
        data = request.json

        roles_data = load_roles()
        role_index = None

        for i, role in enumerate(roles_data['roles']):
            if role['id'] == role_id:
                role_index = i
                break

        if role_index is None:
            return jsonify({'success': False, 'message': 'Role not found'}), 404

        role = roles_data['roles'][role_index]
        votes_data = load_votes()
        role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role_id]
        has_votes = len(role_votes) > 0
    except Exception as e:
        import traceback
        print(f"Error loading role data: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error loading role: {str(e)}'}), 500

    # Update status if provided
    if 'status' in data:
        new_status = data['status']
        if new_status in ['active', 'fulfilled', 'expired']:
            role['status'] = new_status

    # Update position if provided
    if 'position' in data:
        position = data['position'].strip()
        if position:
            role['position'] = position

    # Update candidates if provided (can only add, not remove if votes exist)
    if 'candidates' in data:
        new_candidates = data['candidates']

        if has_votes:
            # Can only add, not remove
            existing_candidate_ids = set(c['id'] for c in role['candidates'])
            voted_candidate_ids = set(v['candidate_id'] for v in role_votes)

            # Build new candidates list preserving IDs
            valid_candidates = []
            existing_candidates = {c['id']: c for c in role['candidates']}
            max_id = max([int(c['id']) for c in role['candidates']], default=0)

            for candidate in new_candidates:
                if isinstance(candidate, dict):
                    candidate_id = candidate.get('id')
                    name = candidate.get('name', '').strip()
                else:
                    candidate_id = None
                    name = str(candidate).strip()

                if not name:
                    continue

                if candidate_id and candidate_id in existing_candidates:
                    valid_candidates.append({'id': candidate_id, 'name': name})
                else:
                    max_id += 1
                    valid_candidates.append({'id': str(max_id), 'name': name})

            # Check we're not removing candidates with votes
            new_candidate_ids = set(c['id'] for c in valid_candidates)
            removed_candidates = voted_candidate_ids - new_candidate_ids

            if removed_candidates:
                return jsonify({
                    'success': False,
                    'message': 'Cannot remove candidates with existing votes'
                }), 400

            role['candidates'] = valid_candidates
        else:
            # No votes, can freely update
            valid_candidates = []
            candidate_id = 1
            for candidate in new_candidates:
                if isinstance(candidate, dict):
                    name = candidate.get('name', '').strip()
                else:
                    name = str(candidate).strip()

                if name:
                    valid_candidates.append({'id': str(candidate_id), 'name': name})
                    candidate_id += 1

            role['candidates'] = valid_candidates

    # Update allowed emails if provided (can add new voters)
    if 'allowed_emails' in data:
        new_emails = data['allowed_emails']
        valid_emails = []

        for email in new_emails:
            email = email.strip()
            if email:
                if '@' not in email or '.' not in email:
                    return jsonify({'success': False, 'message': f'Invalid email format: {email}'}), 400
                valid_emails.append(email)

        if len(valid_emails) > 0:
            role['allowed_emails'] = valid_emails

    # Save updated role
    try:
        role['updated_at'] = datetime.now().isoformat()
        # Use save_role() instead of save_roles() to update only this role
        # save_roles() tries to delete ALL roles which causes foreign key violations
        updated_role = save_role(role)

        return jsonify({
            'success': True,
            'message': 'Role updated successfully',
            'role': updated_role
        })
    except Exception as e:
        import traceback
        print(f"Error saving role: {traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error saving role: {str(e)}'}), 500

@app.route('/api/roles/<role_id>', methods=['DELETE'])
def delete_role(role_id):
    """Delete a role (only if no votes exist)"""
    roles_data = load_roles()
    role_index = None

    for i, role in enumerate(roles_data['roles']):
        if role['id'] == role_id:
            role_index = i
            break

    if role_index is None:
        return jsonify({'success': False, 'message': 'Role not found'}), 404

    # Check if role has votes
    votes_data = load_votes()
    role_votes = [v for v in votes_data['votes'] if v.get('role_id') == role_id]

    if len(role_votes) > 0:
        return jsonify({
            'success': False,
            'message': 'Cannot delete role with existing votes. Mark as expired instead.'
        }), 400

    # Remove role
    deleted_role = roles_data['roles'].pop(role_index)
    save_roles(roles_data)

    return jsonify({
        'success': True,
        'message': f'Role "{deleted_role["position"]}" deleted successfully'
    })

if __name__ == '__main__':
    # Run migration on startup
    migrate_config_to_roles()

    # Get local IP for sharing with collaborators
    import socket

    # Check if running in production or development
    port = int(os.environ.get('PORT', 5001))
    debug = not IS_PRODUCTION

    if debug:
        # Development mode - show helpful URLs
        try:
            # Try to get local IP by connecting to an external address (doesn't actually send data)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            # Fallback to localhost if unable to determine local IP
            local_ip = '127.0.0.1'

        print("\n" + "="*50)
        print("BLIND VOTING SYSTEM")
        print("="*50)
        print(f"\nShare this URL with voters:")
        print(f"  http://{local_ip}:{port}/vote")
        print(f"\nYour results page:")
        print(f"  http://localhost:{port}/results")
        print(f"\nAdmin page (reset votes):")
        print(f"  http://localhost:{port}/admin")
        print("\n" + "="*50 + "\n")

    app.run(host='0.0.0.0', port=port, debug=debug)
