
import streamlit as st
import os
import tempfile
from typing import Dict, List, Optional
import requests
import json
import time
from langfuse.decorators import langfuse_context, observe


langfuse_context.configure(
# TODO: don't hardcode this
  secret_key="sk-lf-6e835f07-2629-4f3d-a31a-8d1802dc19f3", 
  public_key="pk-lf-2fe2b3cc-a75d-4744-9bc7-d50d1ac0f1c6",
  host="https://us.cloud.langfuse.com"
)

class LettaClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.environ.get("LETTA_API_URL", "http://localhost:8283")
        
    # Source Management functions
    @observe()
    def list_sources(self):
        response = requests.get(f"{self.base_url}/v1/sources/")
        response.raise_for_status()
        return response.json()
    
    @observe()
    def get_agent_sources(self, agent_id: str):
        """Get all sources attached to an agent"""
        response = requests.get(f"{self.base_url}/v1/agents/{agent_id}/sources")
        response.raise_for_status()
        return response.json()

    @observe()
    def upload_file_to_source(self, source_id: str, file_path: str):
        """Upload a file to an existing source"""
        filename = os.path.basename(file_path)
        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            # Note: source_id is included in the URL path, not as a form field
            response = requests.post(
                f"{self.base_url}/v1/sources/{source_id}/upload", 
                files=files
            )
        response.raise_for_status()
        return response.json()
    
    @observe()
    def attach_source_to_agent(self, agent_id: str, source_id: str):
        response = requests.patch(
            f"{self.base_url}/v1/agents/{agent_id}/sources/attach/{source_id}"
        )
        response.raise_for_status()
        return response.json()
    
    # Agent functions
    @observe()
    def list_agents(self):
        max_retries = 5
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/v1/agents/")
                response.raise_for_status()
                return response.json()
            except requests.exceptions.ConnectionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
                    
    @observe()
    def send_message(self, agent_id: str, message: str, stream: bool = False):
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "stream": stream
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/v1/agents/{agent_id}/messages",
                json=payload
            )
            response.raise_for_status()
            langfuse_context.score_current_trace(
            name="feedback-on-trace-from-nested-span",
            value=1,
            comment="This answer is legally sound",
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error sending message: {str(e)}")
            print(f"Response content: {e.response.content if hasattr(e, 'response') else 'No response content'}")
            raise
            
    @observe()
    def get_agent_messages(self, agent_id: str):
        response = requests.get(f"{self.base_url}/v1/agents/{agent_id}/messages")
        response.raise_for_status()
        return response.json()
    
    # create agent
    @observe()
    def create_agent(self, name: str, block_value: str):
        #load agent_config.json  
        with open('config/agent_config.json', 'r') as f:
            agent_config = json.load(f)
        agent_config['name'] = name
        response = requests.post(f"{self.base_url}/v1/agents/", json=agent_config)
        response.raise_for_status()
        agent_id = response.json()['id']
        block_response = self._create_block(block_value)
        block_id = block_response['id']
        self._attach_block_to_agent(agent_id, block_id)
        tool_id = "tool-191775ea-c529-40c0-80b7-68cd3ed346eb"
        self.attach_tool(agent_id,tool_id)
        return response.json()
    
    @observe()
    def _create_block(self, block_value: str):
        with open('config/block_config.json', 'r') as f:
            block_config = json.load(f)
        block_config['value'] = block_value
        response = requests.post(f"{self.base_url}/v1/blocks", json=block_config)
        response.raise_for_status()
        return response.json()
    
    @observe()
    def _attach_block_to_agent(self, agent_id: str, block_id: str):
        response = requests.patch(f"{self.base_url}/v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}")
        response.raise_for_status()
        return response.json()
    
    @observe()
    def delete_agent(self, agent_id: str):
        response = requests.delete(f"{self.base_url}/v1/agents/{agent_id}")
        response.raise_for_status()
        return response.json()
    
    @observe()
    def attach_tool(self, agent_id: str, tool_id: str):
        response = requests.patch(f"{self.base_url}/v1/agents/{agent_id}/tools/attach/{tool_id}")
        response.raise_for_status()
        return response.json()
    
    @observe()
    def create_tool(self):
        with open('config/tool_config.json', 'r') as f:
            tool_config = json.load(f)
        response = requests.post(f"{self.base_url}/v1/tools/", json=tool_config)
        response.raise_for_status()
        return response.json()