# Setup Product Requirements Document

## Overview
This document outlines the product requirements for the setup of an agentic virtual assisstant to assist a human in solving the New York Time Connection Puzzle. 

## Constraints
- Use the latest versions of packages.
- Do not specify verions of packages unless absolutely necessary.

## User Stories
| User Story ID | Description| Acceptance Criteria|
|---------------|-----------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| SETUP00| As a developer I want to virtual envionment for the project so that I can manage dependencies. | - A virtual environment should be created using `venv` or `virtualenv`.<br>- The virtual environment should be activated.<br>- The `requirements.txt` file should be created and include all necessary dependencies for the project.<br>- The virtual environment should be documented in the README file.   | 
| SETUP01 | As a developer I want to use Quart as the web framework so that I can build a web application. | - Quart should be installed in the virtual environment.<br>- The Quart server should be documented in the README file.|
| SETUP02 | As a developer I want to use openai, langchain with openai support and langgraph | - required packages should be installed in the virtual environment.<br>- The packages should be documented in the README file.|
| SETUP03 | As a developer I want to use pytest for testing so that I can ensure the application works as expected. | - Pytest should be installed in the virtual environment.<br>- The test suite should be documented in the README file.|
| SETUP04 | As a developer I want to have my code version controlled. | - project is initialized to use git.<br>- default branch is called "main"<br>- project has a .gitignore file for a python project on a MacOS platform. |