from quart import Quart, render_template, request, jsonify
import os
import json

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
            return jsonify({
                "remaining_words": puzzle_state["remaining_words"],
                "status": puzzle_state["status"]
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/recommend", methods=["GET"])
async def get_recommendation():
    """Get the next recommendation (WEB03)"""
    # In a real implementation, this would call the AI recommender
    # For now, just use a placeholder
    recommended_group = puzzle_state["remaining_words"][:4] if len(puzzle_state["remaining_words"]) >= 4 else []
    connection_reason = "These words appear to be related (placeholder recommendation)"
    
    return jsonify({
        "recommended_group": recommended_group,
        "connection_reason": connection_reason,
        "recommender": puzzle_state["active_recommender"]
    })

@app.route("/feedback", methods=["POST"])
async def process_feedback():
    """Process feedback on the recommended group (WEB04)"""
    data = await request.get_json()
    color = data.get("color", "")
    response = data.get("response", "")
    group = data.get("group", [])
    
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
    elif response == "one-away" or response == "not-correct":
        # Handle invalid group
        puzzle_state["invalid_groups"].append({
            "words": group,
            "reason": data.get("reason", ""),
            "error_type": response
        })
    
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
    
    return jsonify({
        "recommended_group": group,
        "connection_reason": reason,
        "status": "Manual override applied"
    })

@app.route("/terminate", methods=["POST"])
async def terminate():
    """Terminate the puzzle-solving process (WEB08)"""
    # In a real implementation, this would properly shut down the app
    # For demo purposes, we'll just update the status
    puzzle_state["status"] = "Terminated"
    return jsonify({
        "status": "Terminated",
        "message": "Puzzle solving terminated"
    })

if __name__ == "__main__":
    app.run(debug=True, use_reloader=True, port=5000, host="0.0.0.0")