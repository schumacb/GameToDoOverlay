import uuid
from datetime import datetime
import nltk 

class BaseTaskParser:
    """
    Abstract base class for task parsers.
    Defines the contract for parsing text into a structured task format.
    """
    def parse(self, text_block: str) -> list:
        raise NotImplementedError("Subclasses must implement the parse method.")

class NltkTaskParser(BaseTaskParser):
    """
    A task parser that uses NLTK to tokenize lines into sentences (steps)
    for each task (line). The first sentence of a line becomes the task title.
    """
    def parse(self, text_block: str) -> list:
        parsed_tasks = []
        lines = text_block.strip().splitlines()
        current_time = datetime.now()

        for line_content in lines:
            original_line = line_content.strip()
            if not original_line: 
                continue
            
            task_id_str = str(uuid.uuid4())
            
            try:
                sentences = nltk.sent_tokenize(original_line)
            except LookupError as e: 
                print(f"NLTK LookupError during parsing task: '{original_line}'. Error: {e}")
                sentences = [original_line] 
            except Exception as e: 
                print(f"General error tokenizing task: '{original_line}'. Error: {e}")
                sentences = [original_line]

            if not sentences: # Should not happen if original_line is not empty
                task_title_str = original_line # Fallback title
                sentences = [original_line]
            else:
                task_title_str = sentences[0] # Use the first sentence as the title

            current_main_task = {
                "task_id": task_id_str,
                "task_title": task_title_str, # First sentence is the title
                "original_text_block": original_line, # Store the full original line if needed
                "created_timestamp": current_time, 
                "steps": []
            }
            
            # All tokenized sentences become steps
            for i, sentence_text in enumerate(sentences):
                if not sentence_text.strip(): 
                    continue
                
                step = {
                    "step_id": str(uuid.uuid4()),
                    "step_index": i,
                    "text": sentence_text.strip(),
                    "completed": False,
                    "completed_timestamp": None,
                }
                current_main_task["steps"].append(step)
            
            if current_main_task["steps"]:
                parsed_tasks.append(current_main_task)
                
        return parsed_tasks