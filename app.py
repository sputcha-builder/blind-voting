from flask import Flask, render_template, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

VOTES_FILE = 'votes.json'
CONFIG_FILE = 'config.json'

def load_votes():
    """Load votes from JSON file"""
    if os.path.exists(VOTES_FILE):
        with open(VOTES_FILE, 'r') as f:
            return json.load(f)
    return {'votes': [], 'voters': []}

def save_votes(data):
    """Save votes to JSON file"""
    with open(VOTES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_config():
    """Load configuration from JSON file"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'candidate_name': '',
        'position': '',
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
    return 3  # Default fallback

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
    """Submit a vote"""
    data = request.json
    voter_email = data.get('voter_email', '').strip().lower()
    choice = data.get('choice', '')

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

    if choice not in ['Inclined', 'Not Inclined']:
        return jsonify({'success': False, 'message': 'Invalid choice'}), 400

    # Load existing votes
    votes_data = load_votes()

    # Check if voter already voted
    if voter_email in votes_data['voters']:
        return jsonify({'success': False, 'message': 'You have already voted'}), 400

    # Add vote
    votes_data['votes'].append({
        'voter': voter_email,
        'choice': choice,
        'timestamp': datetime.now().isoformat()
    })
    votes_data['voters'].append(voter_email)

    # Save votes
    save_votes(votes_data)

    total_voters = get_total_voters()
    return jsonify({
        'success': True,
        'message': f'Vote recorded! {len(votes_data["votes"])}/{total_voters} votes submitted.'
    })

@app.route('/results')
def results_page():
    """Display results page"""
    return render_template('results.html')

@app.route('/api/results', methods=['GET'])
def get_results():
    """Get voting results (only if all votes are in)"""
    config = load_config()
    votes_data = load_votes()
    total_votes = len(votes_data['votes'])
    total_voters = get_total_voters()

    if total_votes < total_voters:
        return jsonify({
            'complete': False,
            'votes_received': total_votes,
            'votes_needed': total_voters,
            'message': f'Waiting for {total_voters - total_votes} more vote(s)',
            'candidate_name': config.get('candidate_name', ''),
            'position': config.get('position', ''),
            'is_configured': config.get('is_configured', False)
        })

    # Count votes
    inclined = sum(1 for v in votes_data['votes'] if v['choice'] == 'Inclined')
    not_inclined = sum(1 for v in votes_data['votes'] if v['choice'] == 'Not Inclined')

    return jsonify({
        'complete': True,
        'total_votes': total_votes,
        'inclined': inclined,
        'not_inclined': not_inclined,
        'votes': votes_data['votes'],
        'candidate_name': config.get('candidate_name', ''),
        'position': config.get('position', ''),
        'is_configured': config.get('is_configured', False)
    })

@app.route('/admin')
def admin_page():
    """Admin page for managing votes"""
    return render_template('admin.html')

@app.route('/api/reset', methods=['POST'])
def reset_votes():
    """Reset all votes and configuration (admin only)"""
    save_votes({'votes': [], 'voters': []})
    save_config({
        'candidate_name': '',
        'position': '',
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

    return jsonify({
        'total_votes': len(votes_data['votes']),
        'votes_needed': total_voters,
        'voters': votes_data['voters'],
        'is_configured': config.get('is_configured', False),
        'candidate_name': config.get('candidate_name', ''),
        'position': config.get('position', ''),
        'voting_locked': len(votes_data['votes']) > 0
    })

@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    config = load_config()
    votes_data = load_votes()

    return jsonify({
        'candidate_name': config.get('candidate_name', ''),
        'position': config.get('position', ''),
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

    candidate_name = data.get('candidate_name', '').strip()
    position = data.get('position', '').strip()
    allowed_emails = data.get('allowed_emails', [])

    # Validate inputs
    if not candidate_name:
        return jsonify({'success': False, 'message': 'Candidate name is required'}), 400

    if not position:
        return jsonify({'success': False, 'message': 'Position is required'}), 400

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
        'candidate_name': candidate_name,
        'position': position,
        'allowed_emails': valid_emails,
        'is_configured': True
    }
    save_config(config_data)

    return jsonify({
        'success': True,
        'message': f'Configuration saved! {len(valid_emails)} voter(s) configured.'
    })

if __name__ == '__main__':
    # Get local IP for sharing with collaborators
    import socket

    # Check if running in production or development
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_ENV') != 'production'

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
