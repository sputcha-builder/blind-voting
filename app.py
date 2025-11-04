from flask import Flask, render_template, request, jsonify, redirect
import json
import os
from datetime import datetime

app = Flask(__name__)

VOTES_FILE = 'votes.json'
CONFIG_FILE = 'config.json'

# Detect if running in production (Render sets PORT environment variable)
IS_PRODUCTION = 'RENDER' in os.environ or os.environ.get('PORT') == '10000'

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

def load_votes():
    """Load votes from JSON file"""
    if os.path.exists(VOTES_FILE):
        with open(VOTES_FILE, 'r') as f:
            return json.load(f)
    return {'votes': []}

def save_votes(data):
    """Save votes to JSON file"""
    with open(VOTES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    """Load configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Migrate old format to new format if needed
            if 'candidate_name' in config and 'candidates' not in config:
                # Old format - convert to new
                if config.get('candidate_name'):
                    config['candidates'] = [{'id': '1', 'name': config['candidate_name']}]
                else:
                    config['candidates'] = []
                del config['candidate_name']
            return config
    return {
        'position': '',
        'candidates': [],
        'allowed_emails': [],
        'is_configured': False
    }

def save_config(data):
    """Save configuration to JSON file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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
    """Save voting configuration"""
    data = request.json

    # Check if voting has started
    votes_data = load_votes()
    if len(votes_data['votes']) > 0:
        return jsonify({
            'success': False,
            'message': 'Cannot change configuration after voting has started. Reset votes first.'
        }), 400

    position = data.get('position', '').strip()
    candidates = data.get('candidates', [])
    allowed_emails = data.get('allowed_emails', [])

    # Validate inputs
    if not position:
        return jsonify({'success': False, 'message': 'Position is required'}), 400

    # Validate candidates
    if not candidates or len(candidates) == 0:
        return jsonify({'success': False, 'message': 'At least one candidate is required'}), 400

    valid_candidates = []
    for i, candidate in enumerate(candidates):
        if isinstance(candidate, dict):
            name = candidate.get('name', '').strip()
        else:
            name = str(candidate).strip()

        if not name:
            continue

        valid_candidates.append({
            'id': str(i + 1),
            'name': name
        })

    if len(valid_candidates) == 0:
        return jsonify({'success': False, 'message': 'At least one candidate is required'}), 400

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

if __name__ == '__main__':
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
