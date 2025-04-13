# Workflow Manager Product Requirements Document (PRD)

## Overview
This document outlines the product requirements for the workflow manager of an agentic virtual assisstant to assist a human in solving the New York Time Connection Puzzle.  The assisant will be able to read the puzzle, make recommendations, and provide feedback on the recommendations to the human.  The assistant uses generative AI technologies to provide the recommendations modify recommendations based on the feedback.  

## Technical Requirements
- The workflow manager should be implemented in Python.
- The workflow manager should be able to handle asynchronous processing.
- The workflow manager should be able to interact with a large language model (LLM) interface.
- The workflow manager should be able to handle human-in-the-loop inputs for setup and responses.
- The workflow manager should be able to create a langgraph workflow graph with nodes and edges.

## User Stories

| User Story ID | Description                                                                 | Acceptance Criteria                                                                                                                                                                                                                     |
|---------------|-----------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| US001         | As a user, I want the system to plan the next steps for solving a puzzle.  | - The `run_planner` function should log the current puzzle state and instructions.<br>- It should use the LLM interface to determine the next action.<br>- The next action should be stored in the `tool_to_use` field of the state.     |
| US002         | As a user, I want the system to decide the next action based on the tool.  | - The `determine_next_action` function should return the tool to use based on the `tool_to_use` field.<br>- If the tool is "ABORT", it should raise an error.<br>- If the tool is "END", it should return the `END` constant.            |
| US003         | As a user, I want the system to execute a workflow to solve puzzles.       | - The `run_workflow` function should process the workflow graph asynchronously.<br>- It should handle human-in-the-loop inputs for setup and responses.<br>- It should update the workflow state based on user inputs and recommendations. |
| US004         | As a user, I want the system to create a workflow graph for solving puzzles. | - The `create_workflow_graph` function should define nodes for all puzzle-solving steps.<br>- It should add conditional edges based on the next action.<br>- It should set "run_planner" as the entry point and use a memory checkpoint.   |
| US005         | As a user, I want a simplified workflow graph for a web interface.         | - The `create_webui_workflow_graph` function should define nodes for key puzzle-solving steps.<br>- It should exclude the "setup_puzzle" node.<br>- It should set "run_planner" as the entry point and use a memory checkpoint.            |