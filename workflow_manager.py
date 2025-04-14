"""
Workflow Manager for Connection Puzzle Solver

This module implements the workflow management system for the puzzle solver,
handling the flow between different tools and processing steps.
"""

import logging
import asyncio
import json
import numpy as np
from typing import Dict, Any, Callable, List, Optional, Tuple

from langchain_core.messages import HumanMessage
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Define constants
OPENAI_MODEL = "gpt-4-turbo"
EMBEDDING_MODEL = "text-embedding-3-small"
MAX_ERRORS = 3
RETRY_LIMIT = 5

# Define state type structure
class PuzzleState(dict):
    """Type definition for the puzzle state."""
    puzzle_status: str
    tool_status: str
    mistake_count: int
    retry_count: int
    remaining_words: List[str]
    correct_groups: Dict[str, List[Dict[str, Any]]]
    invalid_groups: List[Dict[str, Any]]
    active_recommender: str
    tool_to_use: str
    recommendations: Dict[str, Any]
    word_embeddings: Dict[str, List[float]]


async def setup_puzzle(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize the puzzle with necessary setup.
    
    This function sets up the initial puzzle state, generates vocabularies and 
    embeddings for all words.
    """
    logger.info("Setting up puzzle...")
    
    # Ensure remaining_words is populated
    if not state.get("remaining_words"):
        state["puzzle_status"] = "error"
        state["tool_status"] = "setup_failed"
        logger.error("No words provided for puzzle setup")
        return state
        
    # Initialize embeddings
    try:
        embeddings_model = OpenAIEmbeddings(model=EMBEDDING_MODEL)
        word_list = state.get("remaining_words", [])
        
        # Generate embeddings for each word
        logger.info(f"Generating embeddings for {len(word_list)} words...")
        word_embeddings_list = await embeddings_model.aembed_documents(word_list)
        
        # Store embeddings in state
        state["word_embeddings"] = {word: embedding for word, embedding in zip(word_list, word_embeddings_list)}
        
        # Set status
        state["puzzle_status"] = "active"
        state["tool_status"] = "setup_complete"
        state["active_recommender"] = "embedding"
        logger.info("Puzzle setup complete")
        
    except Exception as e:
        state["puzzle_status"] = "error"
        state["tool_status"] = "setup_failed"
        logger.error(f"Error during puzzle setup: {e}")
    
    return state


async def get_embedvec_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate recommendations based on word embedding similarity.
    
    This function analyzes word embeddings to find potentially related groups.
    """
    logger.info("Generating embedding-based recommendations...")
    
    remaining_words = state.get("remaining_words", [])
    word_embeddings = state.get("word_embeddings", {})
    invalid_groups = state.get("invalid_groups", [])
    
    if not remaining_words or len(remaining_words) < 4:
        state["puzzle_status"] = "insufficient_words"
        return state
        
    if not word_embeddings:
        state["puzzle_status"] = "error"
        state["tool_status"] = "embeddings_missing"
        return state
        
    try:
        # Get candidate groups based on embedding similarity
        candidate_groups = await get_candidate_groups(remaining_words, word_embeddings, invalid_groups)
        
        if not candidate_groups:
            state["active_recommender"] = "llm"
            state["tool_to_use"] = "get_llm_recommendation"
            return state
            
        # Take the top group
        top_group = candidate_groups[0]["words"]
        
        # Validate with LLM to get connection reason
        llm = ChatOpenAI(model=OPENAI_MODEL)
        connection_prompt = f"""
        These four words appear to be related: {', '.join(top_group)}
        What is the connection between them? Provide a concise, specific explanation.
        """
        
        response = await llm.ainvoke([HumanMessage(content=connection_prompt)])
        connection_reason = response.content.strip()
        
        # Update state
        state["recommendations"] = {
            "group": top_group,
            "reason": connection_reason,
            "source": "embedding"
        }
        state["active_recommender"] = "embedding"
        state["tool_to_use"] = "apply_recommendation"
        
        logger.info(f"Embedding recommendation: {top_group} - {connection_reason}")
        
    except Exception as e:
        logger.error(f"Error in embedding recommendation: {e}")
        state["active_recommender"] = "llm"
        state["tool_to_use"] = "get_llm_recommendation"
        
    return state


async def get_llm_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate recommendations using the LLM.
    
    This function uses the LLM to find groups of related words and their connections.
    """
    logger.info("Generating LLM-based recommendations...")
    
    remaining_words = state.get("remaining_words", [])
    invalid_groups = state.get("invalid_groups", [])
    retry_count = state.get("retry_count", 0)
    
    if not remaining_words or len(remaining_words) < 4:
        state["puzzle_status"] = "insufficient_words"
        return state
        
    try:
        # Format invalid groups for LLM context
        invalid_groups_str = ""
        for group in invalid_groups:
            words_str = ", ".join(group.get("words", []))
            invalid_groups_str += f"- {words_str}\n"
            
        # Create LLM prompt
        prompt = f"""
        You are helping solve a New York Times Connection puzzle.
        
        The goal is to find groups of 4 words that share a common theme or connection.
        
        Words remaining: {', '.join(remaining_words)}
        
        Invalid groups already tried:
        {invalid_groups_str if invalid_groups_str else "None yet."}
        
        Find ONE group of exactly 4 words that are related to each other from the remaining words.
        Respond with a JSON object with two keys:
        1. "words": a list of exactly 4 words
        2. "connection": a concise explanation of how they are connected
        """
        
        llm = ChatOpenAI(model=OPENAI_MODEL)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Extract JSON response
        content = response.content
        # Find JSON content (between { and })
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = content[json_start:json_end]
            recommendation = json.loads(json_content)
            
            # Validate recommendation
            recommended_words = recommendation.get("words", [])
            connection = recommendation.get("connection", "")
            
            # Check if all words are in remaining_words
            if not all(word in remaining_words for word in recommended_words):
                raise ValueError("Recommendation contains words not in remaining list")
                
            if len(recommended_words) != 4:
                raise ValueError("Recommendation must contain exactly 4 words")
                
            # Update state
            state["recommendations"] = {
                "group": recommended_words,
                "reason": connection,
                "source": "llm"
            }
            state["active_recommender"] = "llm"
            state["tool_to_use"] = "apply_recommendation"
            state["retry_count"] = 0  # Reset retry count on success
            
            logger.info(f"LLM recommendation: {recommended_words} - {connection}")
            
        else:
            raise ValueError("Could not extract JSON from LLM response")
            
    except Exception as e:
        logger.error(f"Error in LLM recommendation: {e}")
        state["retry_count"] = retry_count + 1
        
        if state["retry_count"] > RETRY_LIMIT:
            state["active_recommender"] = "manual"
            state["tool_to_use"] = "get_manual_recommendation"
        
    return state


async def get_manual_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Set up for manual recommendation by a human.
    
    This function prepares the state for receiving manual input.
    """
    logger.info("Setting up for manual recommendation...")
    
    # This function doesn't actually get the input - it just sets up the state
    # The actual input will come from the web UI
    state["active_recommender"] = "manual"
    
    # In a real implementation, we would wait for user input
    # For now, we'll just set a placeholder
    state["recommendations"] = {
        "group": [],
        "reason": "",
        "source": "manual",
        "pending": True
    }
    
    logger.info("Ready for manual recommendation")
    return state


async def one_away_analyzer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze incorrect recommendations that are one word away from being correct.
    
    This function identifies and validates "one-away" groups.
    """
    logger.info("Analyzing one-away errors...")
    
    remaining_words = state.get("remaining_words", [])
    invalid_groups = state.get("invalid_groups", [])
    
    # Find the most recent one-away error
    one_away_errors = [g for g in invalid_groups if g.get("error_type") == "one-away"]
    
    if not one_away_errors:
        # No one-away errors to analyze
        state["active_recommender"] = "embedding"
        state["tool_to_use"] = "get_embedvec_recommendation"
        return state
    
    latest_error = one_away_errors[-1]
    error_words = latest_error.get("words", [])
    
    try:
        # Ask LLM to suggest a correction
        prompt = f"""
        In the New York Times Connection puzzle, this group was marked as "one-away" (one word away from being correct):
        {', '.join(error_words)}
        
        "One-away" means that 3 of these words form a valid group with one additional word from the remaining words.
        
        Remaining words: {', '.join(remaining_words)}
        
        Identify which 3 words from the original group form a theme, and which word from the remaining words completes the group.
        Respond with a JSON object with two keys:
        1. "words": a list of exactly 4 words (3 from original group + 1 from remaining)
        2. "connection": a concise explanation of how they are connected
        """
        
        llm = ChatOpenAI(model=OPENAI_MODEL)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Extract JSON response
        content = response.content
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = content[json_start:json_end]
            recommendation = json.loads(json_content)
            
            # Validate recommendation
            recommended_words = recommendation.get("words", [])
            connection = recommendation.get("connection", "")
            
            # Ensure the recommended words are valid
            if not all(word in remaining_words or word in error_words for word in recommended_words):
                raise ValueError("Recommendation contains invalid words")
                
            if len(recommended_words) != 4:
                raise ValueError("Recommendation must contain exactly 4 words")
                
            # Update state
            state["recommendations"] = {
                "group": recommended_words,
                "reason": connection,
                "source": "one_away_analyzer"
            }
            state["active_recommender"] = "one_away_analyzer"
            state["tool_to_use"] = "apply_recommendation"
            
            logger.info(f"One-away recommendation: {recommended_words} - {connection}")
        
        else:
            raise ValueError("Could not extract JSON from LLM response")
            
    except Exception as e:
        logger.error(f"Error in one-away analysis: {e}")
        state["active_recommender"] = "embedding"
        state["tool_to_use"] = "get_embedvec_recommendation"
        
    return state


async def apply_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply the current recommendation and update the puzzle state.
    
    This function processes user feedback and updates the puzzle state.
    """
    logger.info("Applying recommendation...")
    
    # In a real implementation, this would receive feedback from the user
    # For now, we'll just update the state to continue the flow
    state["tool_to_use"] = "run_planner"
    
    # Check if we're waiting for user feedback
    if state.get("recommendations", {}).get("pending", False):
        logger.info("Waiting for user feedback")
        return state
        
    # Check if we've solved the puzzle
    if not state.get("remaining_words") or len(state.get("remaining_words", [])) < 4:
        logger.info("Puzzle solved!")
        state["puzzle_status"] = "solved"
        state["tool_to_use"] = "END"
        
    # Check if we've hit the error limit
    mistake_count = state.get("mistake_count", 0)
    if mistake_count >= MAX_ERRORS:
        logger.info(f"Maximum errors reached: {mistake_count}")
        state["puzzle_status"] = "max_errors"
        state["tool_to_use"] = "END"
        
    return state


async def get_candidate_groups(
    words: List[str], 
    embeddings: Dict[str, List[float]], 
    invalid_groups: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Generate candidate groups based on embedding similarity.
    
    This function finds groups of similar words by analyzing embedding similarity.
    """
    logger.info(f"Generating candidate groups from {len(words)} words...")
    
    # Calculate similarity matrix
    similarity_matrix = {}
    for word1 in words:
        similarity_matrix[word1] = {}
        embedding1 = embeddings.get(word1)
        if not embedding1:
            continue
            
        for word2 in words:
            if word1 == word2:
                continue
                
            embedding2 = embeddings.get(word2)
            if not embedding2:
                continue
                
            # Calculate cosine similarity
            similarity = np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
            similarity_matrix[word1][word2] = similarity
    
    # For each word, find top 3 most similar words
    candidate_groups = []
    for word in words:
        if word not in similarity_matrix:
            continue
            
        similar_words = sorted(
            similarity_matrix[word].items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:3]
        
        group_words = [word] + [w for w, _ in similar_words]
        
        # Calculate group metric (average similarity between all pairs)
        group_metric = 0
        pair_count = 0
        
        for i in range(len(group_words)):
            for j in range(i + 1, len(group_words)):
                w1, w2 = group_words[i], group_words[j]
                if w1 in similarity_matrix and w2 in similarity_matrix[w1]:
                    group_metric += similarity_matrix[w1][w2]
                    pair_count += 1
                    
        if pair_count > 0:
            group_metric /= pair_count
            
            # Create a unique identifier for the group (sorted words)
            group_id = "_".join(sorted(group_words))
            
            # Check if this group has been marked invalid
            is_invalid = False
            for invalid_group in invalid_groups:
                invalid_words = set(invalid_group.get("words", []))
                if set(group_words) == invalid_words:
                    is_invalid = True
                    break
                    
            if not is_invalid:
                candidate_groups.append({
                    "words": group_words,
                    "metric": group_metric,
                    "id": group_id
                })
    
    # Remove duplicates based on group ID
    unique_groups = {}
    for group in candidate_groups:
        if group["id"] not in unique_groups or group["metric"] > unique_groups[group["id"]]["metric"]:
            unique_groups[group["id"]] = group
    
    # Sort by metric
    sorted_groups = sorted(
        unique_groups.values(), 
        key=lambda x: x["metric"], 
        reverse=True
    )
    
    logger.info(f"Generated {len(sorted_groups)} candidate groups")
    return sorted_groups


async def run_planner(state: Dict[str, Any], llm: Optional[ChatOpenAI] = None) -> Dict[str, Any]:
    """
    Plan the next steps for solving the puzzle.
    
    Implementation addresses US001:
    - Logs current puzzle state and instructions
    - Uses LLM to determine next action
    - Stores next action in the tool_to_use field
    """
    logger.info("Running planner with state: %s", state)
    
    # Initialize LLM if not provided
    if llm is None:
        llm = ChatOpenAI(model=OPENAI_MODEL)
    
    # Prepare input for the LLM
    instructions = """
    You are a planner for a Connection Puzzle solver. Based on the current state,
    decide which tool should be used next. Options are:
    - setup_puzzle: Initial puzzle setup
    - get_embedvec_recommendation: Get recommendation using embedding similarity
    - get_llm_recommendation: Get recommendation using LLM
    - get_manual_recommendation: Get recommendation from human
    - one_away_analyzer: Analyze one-away errors
    - apply_recommendation: Apply the current recommendation
    - END: End the workflow
    - ABORT: Abort the workflow due to error
    
    Return a JSON with a single key "tool_to_use" and the selected tool as value.
    """
    
    # Combine instructions with state information
    prompt = f"{instructions}\n\nCurrent state: {state}"
    
    try:
        # Call the LLM to determine the next action
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        
        # Parse the response and update the state
        try:
            content = response.content
            # Extract the tool name - in a real implementation, this would use proper JSON parsing
            if "END" in content:
                state["tool_to_use"] = "END"
            elif "ABORT" in content:
                state["tool_to_use"] = "ABORT"
            elif "setup_puzzle" in content:
                state["tool_to_use"] = "setup_puzzle"
            elif "get_embedvec_recommendation" in content:
                state["tool_to_use"] = "get_embedvec_recommendation"
            elif "get_llm_recommendation" in content:
                state["tool_to_use"] = "get_llm_recommendation"
            elif "get_manual_recommendation" in content:
                state["tool_to_use"] = "get_manual_recommendation"
            elif "one_away_analyzer" in content:
                state["tool_to_use"] = "one_away_analyzer"
            elif "apply_recommendation" in content:
                state["tool_to_use"] = "apply_recommendation"
            else:
                # Default to END if no valid tool is found
                state["tool_to_use"] = "END"
                
            logger.info("Planner decided next tool: %s", state["tool_to_use"])
        except Exception as e:
            logger.error("Failed to parse LLM response: %s", e)
            state["tool_to_use"] = "ABORT"
            
    except Exception as e:
        logger.error("LLM invocation failed: %s", e)
        state["tool_to_use"] = "ABORT"
        
    return state


def determine_next_action(state: Dict[str, Any]) -> str:
    """
    Determine the next action to take based on the tool_to_use field.
    
    Implementation addresses US002:
    - Returns tool to use based on tool_to_use field
    - Raises error if tool is ABORT
    - Returns END constant if tool is END
    """
    tool = state.get("tool_to_use")
    
    if tool == "ABORT":
        error_msg = "Workflow aborted due to error"
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    if tool == "END":
        logger.info("Workflow completed")
        return END
    
    logger.info("Next action: %s", tool)
    return tool


def create_workflow_graph() -> StateGraph:
    """
    Create a workflow graph for solving puzzles.
    
    Implementation addresses US004:
    - Defines nodes for all puzzle-solving steps
    - Adds conditional edges based on the next action
    - Sets run_planner as the entry point and uses a memory checkpoint
    """
    # Initialize the workflow graph with a memory checkpoint
    workflow = StateGraph(PuzzleState)
    
    
    # Add the planner node that decides the next action
    workflow.add_node("run_planner", run_planner)
    
    # Add nodes for each tool/step
    workflow.add_node("setup_puzzle", setup_puzzle)
    workflow.add_node("get_embedvec_recommendation", get_embedvec_recommendation)
    workflow.add_node("get_llm_recommendation", get_llm_recommendation)
    workflow.add_node("get_manual_recommendation", get_manual_recommendation)
    workflow.add_node("one_away_analyzer", one_away_analyzer)
    workflow.add_node("apply_recommendation", apply_recommendation)
    
    # Add edges to connect nodes based on the next action decision
    workflow.add_conditional_edges(
        "run_planner",
        determine_next_action,
        {
            "setup_puzzle": "setup_puzzle",
            "get_embedvec_recommendation": "get_embedvec_recommendation",
            "get_llm_recommendation": "get_llm_recommendation",
            "get_manual_recommendation": "get_manual_recommendation",
            "one_away_analyzer": "one_away_analyzer",
            "apply_recommendation": "apply_recommendation"
        }
    )
    
    # Connect all tool nodes back to the planner
    workflow.add_edge("setup_puzzle", "run_planner")
    workflow.add_edge("get_embedvec_recommendation", "run_planner")
    workflow.add_edge("get_llm_recommendation", "run_planner")
    workflow.add_edge("get_manual_recommendation", "run_planner")
    workflow.add_edge("one_away_analyzer", "run_planner")
    workflow.add_edge("apply_recommendation", "run_planner")
    
    # Set the entry point to the planner
    workflow.set_entry_point("run_planner")
    
    return workflow


def create_webui_workflow_graph() -> StateGraph:
    """
    Create a simplified workflow graph for a web interface.
    
    Implementation addresses US005:
    - Defines nodes for key puzzle-solving steps
    - Excludes the setup_puzzle node
    - Sets run_planner as the entry point and uses a memory checkpoint
    """
    # Initialize the workflow graph with a memory checkpoint
    workflow = StateGraph(PuzzleState)
    
    
    # Add the planner node
    workflow.add_node("run_planner", run_planner)
    
    # Add nodes for web UI relevant steps (excluding setup_puzzle)
    workflow.add_node("get_embedvec_recommendation", get_embedvec_recommendation)
    workflow.add_node("get_llm_recommendation", get_llm_recommendation)
    workflow.add_node("get_manual_recommendation", get_manual_recommendation)
    workflow.add_node("one_away_analyzer", one_away_analyzer)
    workflow.add_node("apply_recommendation", apply_recommendation)
    
    # Add conditional edges from the planner to other nodes
    workflow.add_conditional_edges(
        "run_planner",
        determine_next_action,
        {
            "get_embedvec_recommendation": "get_embedvec_recommendation",
            "get_llm_recommendation": "get_llm_recommendation",
            "get_manual_recommendation": "get_manual_recommendation",
            "one_away_analyzer": "one_away_analyzer",
            "apply_recommendation": "apply_recommendation"
        }
    )
    
    # Connect all tool nodes back to the planner
    workflow.add_edge("get_embedvec_recommendation", "run_planner")
    workflow.add_edge("get_llm_recommendation", "run_planner")
    workflow.add_edge("get_manual_recommendation", "run_planner")
    workflow.add_edge("one_away_analyzer", "run_planner")
    workflow.add_edge("apply_recommendation", "run_planner")
    
    # Set the entry point to the planner
    workflow.set_entry_point("run_planner")
    
    return workflow


async def run_workflow(
    initial_state: Dict[str, Any], 
    workflow_graph: Optional[StateGraph] = None
) -> Dict[str, Any]:
    """
    Execute a workflow to solve puzzles.
    
    Implementation addresses US003:
    - Processes workflow graph asynchronously
    - Handles human-in-the-loop inputs for setup and responses
    - Updates workflow state based on user inputs and recommendations
    """
    # Use the default workflow if none is provided
    if workflow_graph is None:
        workflow_graph = create_workflow_graph()
    
    logger.info("Starting workflow execution with initial state: %s", initial_state)
    
    # Create a compiled version of the workflow
    compiled_workflow = workflow_graph.compile(checkpointer=MemorySaver())
    
    try:
        # Execute the workflow asynchronously
        final_state = await compiled_workflow.arun(initial_state)
        logger.info("Workflow completed with final state: %s", final_state)
        return final_state
    except Exception as e:
        logger.error("Workflow execution failed: %s", e)
        return {
            "status": "error",
            "error": str(e),
            "puzzle_status": "failed"
        }


def initialize_state_from_puzzle_state(puzzle_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert the web UI puzzle state into a workflow state.
    
    This helper function converts the global puzzle_state from the web UI into
    the format expected by the workflow manager.
    """
    return {
        "puzzle_status": puzzle_state.get("status", "Ready"),
        "tool_status": "ready",
        "mistake_count": 0,
        "retry_count": 0,
        "remaining_words": puzzle_state.get("remaining_words", []),
        "correct_groups": puzzle_state.get("correct_groups", {
            "yellow": [],
            "green": [],
            "blue": [],
            "purple": []
        }),
        "invalid_groups": puzzle_state.get("invalid_groups", []),
        "active_recommender": puzzle_state.get("active_recommender", "default"),
        "tool_to_use": "setup_puzzle",
        "recommendations": {},
        "word_embeddings": {}
    }


def update_puzzle_state_from_workflow(puzzle_state: Dict[str, Any], workflow_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update the web UI puzzle state based on workflow state.
    
    This helper function updates the global puzzle_state based on the results of
    the workflow execution.
    """
    # Update remaining words
    puzzle_state["remaining_words"] = workflow_state.get("remaining_words", puzzle_state.get("remaining_words", []))
    
    # Update correct groups
    puzzle_state["correct_groups"] = workflow_state.get("correct_groups", puzzle_state.get("correct_groups", {
        "yellow": [],
        "green": [],
        "blue": [],
        "purple": []
    }))
    
    # Update invalid groups
    puzzle_state["invalid_groups"] = workflow_state.get("invalid_groups", puzzle_state.get("invalid_groups", []))
    
    # Update active recommender
    puzzle_state["active_recommender"] = workflow_state.get("active_recommender", puzzle_state.get("active_recommender", "default"))
    
    # Update status
    puzzle_state["status"] = workflow_state.get("puzzle_status", puzzle_state.get("status", "Ready"))
    
    return puzzle_state


async def get_recommendation_from_workflow(puzzle_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a recommendation using the workflow manager.
    
    This function initializes a workflow state from the puzzle state,
    runs the workflow for one step to get a recommendation, and returns it.
    """
    # Initialize workflow state from puzzle state
    workflow_state = initialize_state_from_puzzle_state(puzzle_state)
    
    # Create a webui workflow graph (skips setup steps)
    workflow_graph = create_webui_workflow_graph()
    
    # Define a custom entry point for recommendation
    if puzzle_state.get("active_recommender") == "embedding":
        workflow_state["tool_to_use"] = "get_embedvec_recommendation"
    elif puzzle_state.get("active_recommender") == "llm":
        workflow_state["tool_to_use"] = "get_llm_recommendation"
    else:
        # Default to run_planner to decide
        workflow_state["tool_to_use"] = "run_planner"
    
    # Execute the workflow for one step to get a recommendation
    compiled_workflow = workflow_graph.compile(checkpointer=MemorySaver())
    
    try:
        # Execute the workflow with a limit of 1 step
        final_state = await compiled_workflow.arun(workflow_state)
        
        # Extract the recommendation
        recommendation = final_state.get("recommendations", {})
        
        return {
            "group": recommendation.get("group", []),
            "reason": recommendation.get("reason", ""),
            "source": recommendation.get("source", "unknown")
        }
    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        return {
            "group": [],
            "reason": f"Error generating recommendation: {str(e)}",
            "source": "error"
        }


async def analyze_one_away(puzzle_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a one-away error using the workflow manager.
    
    This function initializes a workflow state from the puzzle state,
    runs the one_away_analyzer, and returns the recommendation.
    """
    # Initialize workflow state from puzzle state
    workflow_state = initialize_state_from_puzzle_state(puzzle_state)
    workflow_state["tool_to_use"] = "one_away_analyzer"
    
    # Create a simplified workflow just for one-away analysis
    workflow = StateGraph(PuzzleState)
    
    workflow.add_node("one_away_analyzer", one_away_analyzer)
    workflow.set_entry_point("one_away_analyzer")
    
    # Execute the workflow
    compiled_workflow = workflow.compile(checkpointer=MemorySaver())
    
    try:
        # Execute the workflow
        final_state = await compiled_workflow.arun(workflow_state)
        
        # Extract the recommendation
        recommendation = final_state.get("recommendations", {})
        
        return {
            "group": recommendation.get("group", []),
            "reason": recommendation.get("reason", ""),
            "source": recommendation.get("source", "one_away_analyzer")
        }
    except Exception as e:
        logger.error(f"Error analyzing one-away: {e}")
        return {
            "group": [],
            "reason": f"Error analyzing one-away error: {str(e)}",
            "source": "error"
        }
    
create_webui_workflow_graph().compile().get_graph().draw_png("images/connection_solver_embedvec_graph.png")
