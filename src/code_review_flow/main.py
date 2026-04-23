# Patch to disable SSL verification for Coursera
from code_review_flow.patch import disable_ssl_verification
disable_ssl_verification()

from pydantic import BaseModel
from crewai import LLM
from crewai.flow import Flow, listen, start, router, or_, persist
# from typing import Literal, Optional
from code_review_flow.crews.code_review_crew.crew import CodeReviewCrew
import dill
import json

import os
os.environ["CREWAI_TESTING"] = "true"

# define the flow state
class ReviewState(BaseModel):
    # already dive the path to the PR diff file
    pr_file_path: str = "../files/code_changes.txt"
    ### START CODE HERE ###
    pr_content: str = "" # initialize with an empty string
    errors: list = [] # initialize with an empty list
    review_result: dict = {} # set the correct type
    crew_needed: bool = False # set the correct type
    tokens_used: dict = {} # initialize with an empty dict
    final_answer: str = "" # initialize with an empty string
    ### END CODE HERE ###


@persist()
# Define the flow
class PRCodeReviewFlow(Flow[ReviewState]):
    """
    CrewAI Flow for automated code review of pull requests.
    """
    ### START CODE HERE ###
    @start()
    def read_pr_file(self):
        """Read the PR file and determine if crew review is needed"""
        print("🔍 Starting PR Code Review...")
        
        pr_file_path = self.state.pr_file_path
    
        if not pr_file_path:
            self.state.errors.append("Missing 'file_path' in state")
            self.state.final_answer = (
                "There was no file_path set. Please set the 'file_path' in the state and try again."
            )
            print(f"❌ {self.state.final_answer}")
            return
    
        try:
            with open(pr_file_path, "r") as f:
                file_contents = f.read()
    
            # ✅ Save file content in state
            self.state.pr_content = file_contents
    
        except Exception as e:
            error_message = f"There was an error reading the file at {pr_file_path}: \n{str(e)}"
            print(f"❌ {error_message}")
    
            # ✅ Save error
            self.state.errors.append("Error while reading the PR file")
    
            # ✅ Save final answer
            self.state.final_answer = error_message


    
    ### START CODE HERE ###
    @router("read_pr_file")
    def analyze_changes(self, context):
        """Route to appropriate review type based on complexity"""
    
        # ✅ If there were errors earlier → stop flow
        if len(self.state.errors) > 0:
            self.state.final_answer = self.state.final_answer or "Error occurred while reading PR file."
            return "ERROR"
    
        # ✅ Build prompt for LLM decision
        prompt = (
            "Analyze this pull request diff file and respond with exactly one word: SIMPLE or COMPLEX.\n"
            "SIMPLE: small changes that don't compromise code quality or security. "
            "Examples: typos, formatting, small refactoring, documentation.\n"
            "COMPLEX: significant changes needing deeper review. "
            "Examples: new features, logic changes, bug fixes, security-sensitive code.\n"
            f"\nPR Diff:\n{self.state.pr_content}\n"
        )
    
        # ✅ LLM call
        llm = LLM(model="groq/llama-3.3-70b-versatile")
        decision = llm.call(messages=prompt)
    
        # ✅ Route based on decision
        if "COMPLEX" in decision.upper():
            self.state.crew_needed = True
            return "COMPLEX"
        else:
            self.state.crew_needed = False
            return "SIMPLE"


    
    # if the PR is simple, do a simple review
    ### START CODE HERE ###
    @listen("SIMPLE")
    def simple_review(self):
        """Simple review for minor changes"""
        print("⚡ Performing simple review...")
        
        # ✅ Complete prompt with required JSON structure
        prompt = (
            "Analyze this pull request diff file and evaluate the changes.\n"
            "Do not make assumptions about code outside the provided diff.\n\n"
            "Return your response strictly as a JSON object with the following fields:\n"
            "- confidence: integer (0–100) indicating confidence in approving the PR\n"
            "- findings: string summarizing key observations\n"
            "- recommendations: string with suggestions or improvements\n\n"
            f"PR Diff:\n{self.state.pr_content}\n"
        )
    
        # ✅ LLM call
        llm = LLM(model="groq/llama-3.3-70b-versatile")
        result = llm.call(messages=prompt)
    
        # ✅ Save result in state
        self.state.review_result = {"simple_review": result}
    

    
    # if the PR is complex, deploy crew review
    ### START CODE HERE ###
    @listen("COMPLEX")
    def full_crew_review(self):
        """Full crew review for complex changes"""
        print("🚀 Starting full crew review...")
        
        pr_content = self.state.pr_content
    
        # ✅ Instantiate crew
        code_review_crew = CodeReviewCrew().crew()
    
        try:
            # ✅ Kickoff crew with PR content
            result = code_review_crew.kickoff(inputs={'file_content': pr_content})
    
            # ✅ Save structured result
            self.state.review_result = result.json_dict
    
            # ✅ Save token usage (optional but required in state)
            self.state.tokens_used = result.token_usage
    
        except Exception as e:
            error_message = f"There was an error during the crew review: \n{str(e)}"
            print(f"❌ {error_message}")
    
            # ✅ Save error
            self.state.errors.append("Error during crew review")
    
            # ✅ Update final answer
            self.state.final_answer = error_message
    

    # make the final decision based on the review results
    ### START CODE HERE ###
    @listen(or_("simple_review", "full_crew_review"))
    def make_final_decision(self):
        """Make the final decision based on the review results"""
        print("🧐 Making final decision based on review results...")
        
        review_result = self.state.review_result
    
        # ✅ Prompt for final decision
        prompt = (
            "Based on the following analysis of the pull request diff file, "
            "make a final decision on whether to approve the PR for merging.\n"
            "Any review with a confidence score above 85 can be approved, but improvements can be suggested.\n\n"
            "Return a structured response including:\n"
            "- Final Review Decision: APPROVE, REQUEST CHANGES, or ESCALATE\n"
            "- Confidence Score: integer (0-100)\n"
            "- Findings: summary of key findings\n"
            "- If REQUEST CHANGES: list required fixes\n"
            "- If ESCALATE: reasons and possible solutions\n\n"
            f"Analysis:\n{review_result}\n"
        )
    
        # ✅ LLM call
        llm = LLM(model="groq/llama-3.3-70b-versatile")
        final_decision = llm.call(messages=prompt)
    
        # ✅ Save final answer
        self.state.final_answer = final_decision


    # return the final answer
    @listen(or_("ERROR", "make_final_decision"))
    def return_final_answer(self):
        """Return the final answer to the user"""

        print("📝 Final Answer:")
        print(f"{self.state.final_answer}")
        print("\n✨ Automatic code review completed!")
        return self.state.final_answer


def kickoff():
    # ✅ Instantiate flow with tracing enabled
    pr_code_review_flow = PRCodeReviewFlow(tracing=True)

    # ✅ Kickoff the flow with a custom ID (used for persistence)
    result = pr_code_review_flow.kickoff(inputs={"id": "my_code_review_flow"})

    # save the result of the flow - for grading purposes
    with open('../result.dill', 'wb') as f:
        dill.dump(result, f)

    # Save the flow state as JSON - for grading purposes
    with open('../flow_state.json', 'w') as f:
        json.dump(pr_code_review_flow.state.model_dump(), f, indent=2)


def plot():
    pr_code_review_flow = PRCodeReviewFlow()
    pr_code_review_flow.plot()

import subprocess
import sys
import os

def run_ui():
    """Launch Streamlit UI"""
    app_path = os.path.join(os.path.dirname(__file__), "..", "..", "app.py")
    app_path = os.path.abspath(app_path)

    print("🚀 Starting UI...")
    
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", app_path
    ])
if __name__ == "__main__":
    kickoff()