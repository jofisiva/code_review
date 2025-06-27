from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import os
import json
from multi_iteration_orchestrator import MultiIterationReviewOrchestrator
from azure_devops_iteration_client import AzureDevOpsIterationClient
from iterative_improvement_loop import IterativeImprovementLoop, BatchImprovementProcessor
import markdown
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
import difflib

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
        
        if iteration_id:
            iteration_id = int(iteration_id)
        
        # Create the orchestrator
        orchestrator = MultiIterationReviewOrchestrator()
        
        # Handle different review modes
        if review_iterations == 'specific' and iteration_id:
            flash(f'Reviewing specific iteration {iteration_id}', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id), iteration_id=iteration_id)
        elif review_iterations == 'multiple':
            flash('Reviewing all iterations', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id))
        else:
            # Default to latest iteration
            flash('Reviewing latest iteration', 'info')
            review_results = orchestrator.review_pull_request(int(pr_id), latest_only=True)
        
        # Run iterative improvement if requested
        run_improvement = request.form.get('run_improvement') == 'yes'
        if run_improvement:
            flash('Starting iterative code improvement based on review comments', 'info')
            try:
                # Create batch improvement processor
                improvement_processor = BatchImprovementProcessor()
                
                # Set max iterations from form or default to 3
                max_iterations = int(request.form.get('max_iterations', 3))
                
                # Process the pull request for improvements
                improvement_results = improvement_processor.process_pull_request(
                    pull_request_id=int(pr_id),
                    max_iterations=max_iterations
                )
                
                # Save the improvement results ID for later reference
                improvement_id = f"batch_improvement_{pr_id}"
                flash(f'Completed iterative improvement. Processed {improvement_results["files_processed"]} files', 'success')
                
                # Redirect to the improvement results page
                return redirect(url_for('view_improvement', improvement_id=improvement_id))
            except Exception as e:
                flash(f'Error during iterative improvement: {str(e)}', 'error')
        
        # Post comments to Azure DevOps if requested
        if request.form.get('post_comments') == 'yes':
            orchestrator.post_review_comments(int(pr_id), review_results)
            flash('Posted review comments to Azure DevOps', 'info')
        
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

@app.route('/api/iterations', methods=['GET'])
def get_iterations():
    """API endpoint to get iterations for a pull request"""
    pr_id = request.args.get('pr_id')
    if not pr_id:
        return jsonify({'error': 'Missing pull request ID'}), 400
        
    try:
        client = AzureDevOpsIterationClient()
        iterations = client.get_pull_request_iterations(int(pr_id))
        
        # Convert iteration objects to dictionaries
        iteration_data = [{
            'id': iteration.id,
            'author': iteration.author.display_name if iteration.author else 'Unknown',
            'date': iteration.created_date.strftime('%Y-%m-%d %H:%M:%S') if iteration.created_date else 'Unknown',
            'description': f"Iteration {iteration.id}"
        } for iteration in iterations]
        
        return jsonify(iteration_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/improvement_details', methods=['GET'])
def get_improvement_details():
    """API endpoint to get details of file improvements"""
    pr_id = request.args.get('pr_id')
    file_path = request.args.get('file_path')
    
    if not pr_id or not file_path:
        return jsonify({'error': 'Missing required parameters'}), 400
        
    try:
        # Sanitize file path for use in filename
        sanitized_path = file_path.replace('/', '_').replace('\\', '_').replace(':', '_')
        
        # Construct the path to the final improvement file
        improvement_dir = "reviews/improvements"
        final_file_path = os.path.join(improvement_dir, f"final_improvement_{pr_id}_{sanitized_path}.json")
        
        # Check if file exists
        if not os.path.exists(final_file_path):
            return jsonify({'error': 'Improvement details not found'}), 404
            
        # Read the improvement details
        with open(final_file_path, 'r') as f:
            improvement_data = json.load(f)
            
        return jsonify(improvement_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view_improvement/<improvement_id>')
def view_improvement(improvement_id):
    """View the results of an iterative improvement process"""
    try:
        # Extract PR ID from improvement ID
        pr_id = improvement_id.replace('batch_improvement_', '')
        
        # Construct the path to the batch improvement file
        improvement_dir = "reviews/improvements"
        batch_file_path = os.path.join(improvement_dir, f"batch_improvement_{pr_id}.json")
        
        # Check if file exists
        if not os.path.exists(batch_file_path):
            flash('Improvement results not found', 'error')
            return redirect(url_for('index'))
            
        # Read the improvement results
        with open(batch_file_path, 'r') as f:
            improvement_results = json.load(f)
            
        return render_template('improvement.html', improvement_results=improvement_results)
    except Exception as e:
        flash(f'Error loading improvement results: {str(e)}', 'error')
        return redirect(url_for('index'))

def generate_diff_html(old_content, new_content, file_path):
    """Generate HTML diff between old and new content."""
    if old_content is None:
        old_content = ''
    
    # Get file extension for syntax highlighting
    file_ext = os.path.splitext(file_path)[1][1:]
    
    # Create diff
    diff = difflib.HtmlDiff(tabsize=4)
    diff_html = diff.make_table(
        old_content.splitlines(),
        new_content.splitlines(),
        fromdesc="Before",
        todesc="After",
        context=True,
        numlines=3
    )
    
    return diff_html

def highlight_code(code, file_path):
    """Highlight code using Pygments."""
    try:
        # Try to get lexer by file extension
        file_ext = os.path.splitext(file_path)[1][1:]
        if file_ext:
            lexer = get_lexer_by_name(file_ext)
        else:
            # Guess lexer based on content
            lexer = guess_lexer(code)
    except:
        # Default to Python if we can't determine the language
        lexer = get_lexer_by_name('python')
    
    formatter = HtmlFormatter(linenos=True, cssclass="source")
    return highlight(code, lexer, formatter)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
