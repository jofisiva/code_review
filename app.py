"""
Flask web application for the code review system.
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
import difflib

from core.multi_iteration_orchestrator import MultiIterationReviewOrchestrator
from azure_devops.client import AzureDevOpsIterationClient
from core.iterative_improvement_loop import IterativeImprovementLoop, BatchImprovementProcessor
from utils.config import get_config

# Get configuration
config = get_config()
USE_LOCAL_LLM = config.get('USE_LOCAL_LLM', False)
LOCAL_LLM_MODEL = config.get('LOCAL_LLM_MODEL', 'llama3')
LOCAL_LLM_API_URL = config.get('LOCAL_LLM_API_URL', 'http://localhost:11434')
LOCAL_LLM_API_TYPE = config.get('LOCAL_LLM_API_TYPE', 'ollama')

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['REVIEWS_DIR'] = 'reviews'

# Ensure reviews directory exists
os.makedirs(app.config['REVIEWS_DIR'], exist_ok=True)

@app.route('/')
def index():
    """Home page with form to start a new review."""
    # Get available iterations for a PR if requested
    pr_iterations = []
    pr_id_for_iterations = request.args.get('get_iterations_for')
    
    if pr_id_for_iterations:
        try:
            azure_client = AzureDevOpsIterationClient()
            iterations = azure_client.get_pull_request_iterations(int(pr_id_for_iterations))
            for iteration in iterations:
                pr_iterations.append({
                    'id': iteration.id,
                    'created_date': iteration.created_date
                })
        except Exception as e:
            flash(f'Error fetching iterations: {str(e)}', 'error')
    
    # List existing reviews
    reviews = []
    if os.path.exists(app.config['REVIEWS_DIR']):
        for filename in os.listdir(app.config['REVIEWS_DIR']):
            if filename.startswith('complete_review_') and filename.endswith('.json'):
                review_id = filename.replace('complete_review_', '').replace('.json', '')
                try:
                    with open(os.path.join(app.config['REVIEWS_DIR'], filename), 'r') as f:
                        review_data = json.load(f)
                        reviews.append({
                            'id': review_id,
                            'title': review_data.get('title', f'PR #{review_id}'),
                            'created_by': review_data.get('created_by', 'Unknown'),
                            'file_count': len(review_data.get('files', [])),
                            'repository': review_data.get('repository', 'Unknown')
                        })
                except Exception as e:
                    print(f"Error loading review {filename}: {str(e)}")
    
    return render_template('index.html', reviews=reviews)

@app.route('/start_review', methods=['POST'])
def start_review():
    """Start a new code review."""
    pr_id = request.form.get('pr_id')
    
    if not pr_id:
        flash('Please enter a pull request ID', 'error')
        return redirect(url_for('index'))
    
    try:
        # Determine which orchestrator to use
        use_langgraph = request.form.get('use_langgraph') == 'yes'
        review_iterations = request.form.get('review_iterations')
        iteration_id = request.form.get('iteration_id')
        
        # Check if local LLM should be used
        use_local_llm = request.form.get('use_local_llm') == 'yes' or USE_LOCAL_LLM
        
        # Check if comments should be automatically posted to PR
        post_comments = request.form.get('post_comments') == 'yes'
        auto_post_comments = request.form.get('auto_post_comments') == 'yes'
        
        if iteration_id:
            iteration_id = int(iteration_id)
        
        # Create the orchestrator
        orchestrator = MultiIterationReviewOrchestrator(
            use_local_llm=use_local_llm, 
            post_comments=post_comments,
            auto_post_comments=auto_post_comments
        )
        
        # Handle different review modes
        if review_iterations == 'specific' and iteration_id:
            flash(f'Reviewing specific iteration {iteration_id}', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id), iteration_id=iteration_id)
        elif review_iterations == 'all':
            flash('Reviewing all iterations', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id), review_all=True)
        else:
            # Default to latest iteration
            flash('Reviewing latest iteration', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id))
        
        # Run iterative improvement if requested
        run_improvement = request.form.get('run_improvement') == 'yes'
        if run_improvement:
            flash('Starting iterative code improvement based on review comments', 'info')
            try:
                # Create batch improvement processor
                improvement_processor = BatchImprovementProcessor(use_local_llm=use_local_llm)
                
                # Set max iterations from form or default to 3
                max_iterations = int(request.form.get('max_iterations', 3))
                
                # Process the pull request for improvements
                improvement_results = improvement_processor.process_pull_request(
                    pull_request_id=int(pr_id),
                    max_iterations=max_iterations,
                    post_comments=post_comments
                )
                
                # Save the improvement results ID for later reference
                improvement_id = f"batch_improvement_{pr_id}"
                flash(f'Completed iterative improvement. Processed {len(improvement_results)} files', 'success')
                
                # Redirect to the improvement results page
                return redirect(url_for('view_improvement', improvement_id=improvement_id))
            except Exception as e:
                flash(f'Error during iterative improvement: {str(e)}', 'error')
        
        flash('Code review completed successfully', 'success')
        return redirect(url_for('view_review', review_id=pr_id))
    except Exception as e:
        flash(f'Error performing code review: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/review/<review_id>')
def view_review(review_id):
    """View a completed code review."""
    review_path = os.path.join(app.config['REVIEWS_DIR'], f'complete_review_{review_id}.json')
    
    if not os.path.exists(review_path):
        flash('Review not found', 'error')
        return redirect(url_for('index'))
    
    try:
        with open(review_path, 'r') as f:
            review_data = json.load(f)
        
        # Convert markdown to HTML for summary review
        if 'summary_review' in review_data:
            review_data['summary_review_html'] = markdown.markdown(review_data['summary_review'])
        
        return render_template('review.html', review=review_data)
    except Exception as e:
        flash(f'Error loading review: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/review/<review_id>/file/<path:file_path>')
def view_file_review(review_id, file_path):
    """View a specific file review."""
    review_path = os.path.join(app.config['REVIEWS_DIR'], f'complete_review_{review_id}.json')
    
    if not os.path.exists(review_path):
        flash('Review not found', 'error')
        return redirect(url_for('index'))
    
    try:
        with open(review_path, 'r') as f:
            review_data = json.load(f)
        
        # Find the specific file
        file_data = None
        for file_info in review_data.get('files', []):
            if file_info['path'] == file_path:
                file_data = file_info
                break
        
        if not file_data:
            flash('File review not found', 'error')
            return redirect(url_for('view_review', review_id=review_id))
        
        # Generate HTML diff
        diff_html = generate_diff_html(file_data.get('old_content', ''), file_data.get('new_content', ''), file_path)
        
        # Convert markdown to HTML for analyses
        coder_analysis_html = markdown.markdown(file_data.get('coder_analysis', ''))
        reviewer_analysis_html = markdown.markdown(file_data.get('reviewer_analysis', ''))
        
        return render_template('file_review.html', 
                               review_id=review_id, 
                               file_data=file_data,
                               diff_html=diff_html,
                               coder_analysis_html=coder_analysis_html,
                               reviewer_analysis_html=reviewer_analysis_html)
    except Exception as e:
        flash(f'Error loading file review: {str(e)}', 'error')
        return redirect(url_for('view_review', review_id=review_id))

@app.route('/api/reviews')
def api_list_reviews():
    """API endpoint to list all reviews."""
    reviews = []
    if os.path.exists(app.config['REVIEWS_DIR']):
        for filename in os.listdir(app.config['REVIEWS_DIR']):
            if filename.startswith('complete_review_') and filename.endswith('.json'):
                review_id = filename.replace('complete_review_', '').replace('.json', '')
                reviews.append({
                    'id': review_id,
                    'url': url_for('api_get_review', review_id=review_id, _external=True)
                })
    
    return jsonify(reviews)

@app.route('/api/review/<review_id>')
def api_get_review(review_id):
    """API endpoint to get a specific review."""
    review_path = os.path.join(app.config['REVIEWS_DIR'], f'complete_review_{review_id}.json')
    
    if not os.path.exists(review_path):
        return jsonify({'error': 'Review not found'}), 404
    
    try:
        with open(review_path, 'r') as f:
            review_data = json.load(f)
        
        return jsonify(review_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/iterations')
def api_get_iterations():
    """API endpoint to get iterations for a pull request."""
    pr_id = request.args.get('pr_id')
    
    if not pr_id:
        return jsonify({'error': 'Pull request ID is required'}), 400
    
    try:
        orchestrator = MultiIterationReviewOrchestrator()
        iterations = orchestrator.get_pull_request_iterations(int(pr_id))
        return jsonify(iterations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/improvement/<improvement_id>')
def view_improvement(improvement_id):
    """View iterative improvement results."""
    # Extract PR ID from improvement ID
    pr_id = improvement_id.replace('batch_improvement_', '')
    
    # Find all improvement files for this PR
    improvement_files = []
    improvements_dir = os.path.join(app.config['REVIEWS_DIR'], 'improvements')
    
    if os.path.exists(improvements_dir):
        for filename in os.listdir(improvements_dir):
            if filename.endswith('.json') and '_final_' in filename:
                try:
                    with open(os.path.join(improvements_dir, filename), 'r') as f:
                        improvement_data = json.load(f)
                        file_path = filename.split('_final_')[0].replace('_', '/')
                        improvement_files.append({
                            'file_path': file_path,
                            'iterations': improvement_data.get('iterations_completed', 0),
                            'all_resolved': improvement_data.get('all_issues_resolved', False)
                        })
                except Exception as e:
                    print(f"Error loading improvement file {filename}: {str(e)}")
    
    return render_template('improvement.html', 
                           improvement_id=improvement_id,
                           pr_id=pr_id,
                           files=improvement_files)

@app.route('/api/improvement_details')
def api_get_improvement_details():
    """API endpoint to get details of an iterative improvement for a file."""
    file_path = request.args.get('file_path')
    
    if not file_path:
        return jsonify({'error': 'File path is required'}), 400
    
    # Convert file path to safe filename
    safe_filename = file_path.replace('/', '_').replace('\\', '_').replace(':', '_')
    
    # Find the final improvement file
    improvements_dir = os.path.join(app.config['REVIEWS_DIR'], 'improvements')
    final_file = None
    
    if os.path.exists(improvements_dir):
        for filename in os.listdir(improvements_dir):
            if filename.startswith(safe_filename) and '_final_' in filename and filename.endswith('.json'):
                final_file = filename
                break
    
    if not final_file:
        return jsonify({'error': 'Improvement file not found'}), 404
    
    try:
        with open(os.path.join(improvements_dir, final_file), 'r') as f:
            improvement_data = json.load(f)
        
        # Convert reviewer analyses to HTML
        for iteration in improvement_data.get('iterations', []):
            if 'reviewer_analysis' in iteration:
                iteration['reviewer_analysis_html'] = markdown.markdown(iteration['reviewer_analysis'])
        
        return jsonify(improvement_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_diff_html(old_content, new_content, file_path):
    """Generate HTML diff between old and new content."""
    # Determine the lexer based on file extension
    try:
        _, ext = os.path.splitext(file_path)
        lexer = get_lexer_by_name(ext[1:])  # Remove the dot from extension
    except:
        # If we can't determine the lexer from extension, try to guess
        try:
            lexer = guess_lexer(new_content)
        except:
            # Default to Python if we can't guess
            lexer = get_lexer_by_name('python')
    
    # Generate diff
    diff = difflib.unified_diff(
        old_content.splitlines(),
        new_content.splitlines(),
        lineterm=''
    )
    
    # Convert diff to HTML
    formatter = HtmlFormatter(style='colorful')
    diff_html = highlight('\n'.join(diff), lexer, formatter)
    
    # Add CSS for syntax highlighting
    css = formatter.get_style_defs('.highlight')
    diff_html = f'<style>{css}</style>{diff_html}'
    
    return diff_html

if __name__ == '__main__':
    app.run(debug=config.get('DEBUG', False), host='0.0.0.0', port=5000)
