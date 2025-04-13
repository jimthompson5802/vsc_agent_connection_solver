from quart import Quart, render_template, request, jsonify
import os
import json
import workflow_manager as wm  # Import the workflow manager

app = Quart(__name__)

# Global variables to store puzzle state
puzzle_state = {
    "remaining_words": [],
    "correct_groups": {
        "yellow": [],
        "green": [],
        "blue": [],
        "purple": []
    },
    "invalid_groups": [],
    "active_recommender": "default",
    "status": "Ready"
}

@app.route("/")
async def index():
    """Render the main page"""
    return await render_template("index.html", puzzle_state=puzzle_state)

@app.route("/setup", methods=["POST"])
async def setup_puzzle():
    """Setup the puzzle with words from a text file (WEB01, WEB01a)"""
    form = await request.form
    file_path = form.get("puzzle_file", "")
    
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    
    try:
        with open(file_path, "r") as file:
            content = file.read()
            # Parse comma-separated words and convert to lowercase (WEB01a)
            words = [word.strip().lower() for word in content.split(",")]
            puzzle_state["remaining_words"] = words
            puzzle_state["status"] = "Puzzle loaded"
            
            # Initialize the workflow with the loaded puzzle (US001)
            workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
            workflow_state["tool_to_use"] = "setup_puzzle"
            
            # Run the setup_puzzle function directly
            result_state = await wm.setup_puzzle(workflow_state)
            
            # Update the puzzle state with the result
            wm.update_puzzle_state_from_workflow(puzzle_state, result_state)
            
            return jsonify({
                "remaining_words": puzzle_state["remaining_words"],
                "status": puzzle_state["status"]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recommend", methods=["GET"])
async def get_recommendation():
    """Get the next recommendation (WEB03)"""
    try:
        # Get recommendation using the workflow manager (US003, US005)
        recommendation = await wm.get_recommendation_from_workflow(puzzle_state)
        
        # Extract the recommendation details
        recommended_group = recommendation.get("group", [])
        connection_reason = recommendation.get("reason", "")
        source = recommendation.get("source", "unknown")
        
        # Update the active recommender in the puzzle state
        puzzle_state["active_recommender"] = source
        
        return jsonify({
            "recommended_group": recommended_group,
            "connection_reason": connection_reason,
            "recommender": puzzle_state["active_recommender"]
        })
    except Exception as e:
        return jsonify({
            "recommended_group": [],
            "connection_reason": f"Error generating recommendation: {str(e)}",
            "recommender": "error"
        })

@app.route("/feedback", methods=["POST"])
async def process_feedback():
    """Process feedback on the recommended group (WEB04)"""
    data = await request.get_json()
    color = data.get("color", "")
    response = data.get("response", "")
    group = data.get("group", [])
    
    # Initialize workflow state from current puzzle state
    workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
    
    if color in ["yellow", "green", "blue", "purple"]:
        # Handle correct group
        puzzle_state["correct_groups"][color].append({
            "words": group,
            "reason": data.get("reason", "")
        })
        # Remove words from remaining words
        for word in group:
            if word in puzzle_state["remaining_words"]:
                puzzle_state["remaining_words"].remove(word)
                
        # Update workflow state
        workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
        workflow_state["puzzle_status"] = "continue"
        
    elif response == "one-away":
        # Handle one-away error
        puzzle_state["invalid_groups"].append({
            "words": group,
            "reason": data.get("reason", ""),
            "error_type": "one-away"
        })
        
        # Trigger one-away analysis in workflow
        one_away_result = await wm.analyze_one_away(puzzle_state)
        
        # If we got a recommendation, update the puzzle state
        if one_away_result.get("group"):
            puzzle_state["active_recommender"] = "one_away_analyzer"
        
    elif response == "not-correct":
        # Handle invalid group
        puzzle_state["invalid_groups"].append({
            "words": group,
            "reason": data.get("reason", ""),
            "error_type": "not-correct"
        })
        
        # Update workflow state
        workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
        workflow_state["mistake_count"] = workflow_state.get("mistake_count", 0) + 1
        
        # Check if we've reached the error limit
        if workflow_state["mistake_count"] >= wm.MAX_ERRORS:
            workflow_state["puzzle_status"] = "max_errors"
    
    # Apply the workflow state to update the puzzle state
    wm.update_puzzle_state_from_workflow(puzzle_state, workflow_state)
    
    puzzle_state["status"] = f"Feedback processed: {response if response else color}"
    
    return jsonify({
        "remaining_words": puzzle_state["remaining_words"],
        "correct_groups": puzzle_state["correct_groups"],
        "invalid_groups": puzzle_state["invalid_groups"],
        "status": puzzle_state["status"]
    })

@app.route("/override", methods=["POST"])
async def manual_override():
    """Process manual override of recommendation (WEB05)"""
    data = await request.get_json()
    group = data.get("group", [])
    reason = data.get("reason", "")
    
    # Update the workflow state with the manual recommendation
    workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
    workflow_state["recommendations"] = {
        "group": group,
        "reason": reason,
        "source": "manual"
    }
    workflow_state["active_recommender"] = "manual"
    
    # Apply the workflow state
    wm.update_puzzle_state_from_workflow(puzzle_state, workflow_state)
    
    return jsonify({
        "recommended_group": group,
        "connection_reason": reason,
        "status": "Manual override applied"
    })

@app.route("/terminate", methods=["POST"])
async def terminate():
    """Terminate the puzzle-solving process (WEB08)"""
    # Update the workflow state to end
    workflow_state = wm.initialize_state_from_puzzle_state(puzzle_state)
    workflow_state["puzzle_status"] = "terminated"
    workflow_state["tool_to_use"] = "END"
    
    # Apply the workflow state
    wm.update_puzzle_state_from_workflow(puzzle_state, workflow_state)
    
    return jsonify({
        "status": "Terminated",
        "message": "Puzzle solving terminated"
    })

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5000, host="127.0.0.1")