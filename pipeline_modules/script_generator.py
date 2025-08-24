import os
import json
import sys
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from forex_python.converter import CurrencyRates
from pipeline_modules import db_logger

def clean_json_output(raw_response):
    # Remove triple backtick blocks and language tags
    cleaned = re.sub(r"```json\\n|```|```json", "", raw_response, flags=re.IGNORECASE)
    return cleaned.strip()

class ScriptGenerator:
    """
    This class:
    - Loads a prompt template from the file
    - Generates a dialogue script using GPT-4o
    - Saves the script as a json file
    """
    def __init__(self, api_key, prompt_template_path, log_path):
        """
        Sets up the generator with the API key and template path
        """
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key)

        # dynamic resolve file paths relative to proj root
        self.project_root = Path(__file__).resolve().parent.parent
        self.prompt_template_path = self.project_root / prompt_template_path
        self.log_path = self.project_root / log_path
        
        self.prompt_template = self.load_prompt_template(self.prompt_template_path)
        self.df_log = db_logger.init_log(self.log_path)

    
    
    def load_prompt_template(self, path):
        """
        Loads prompt template from files
        """
        with open(path, "r") as file:
            return file.read()
    
    def generate_script(self, topic, tone="educational", account="default_account"):
        """
        Generates the dialogue script using GPT
        
        Steps:
        - Insert topic + tone into the template
        - Sends it to GPT with JSON output mode
        Returns the result as JSON
        """
        prompt = self.prompt_template.replace("[INSERT TOPIC HERE]", topic)
        prompt = prompt.replace("[INSERT TONE HERE, e.g., 'humorous']", tone)

        try:
            # Call GPT
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{
                    "role":"user",
                    "content": prompt
                    }],
                temperature=0.7 # balanced creativity
            )

            # save cost details 
            usage = response.usage
            input_tokens = usage.prompt_tokens
            output_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens

            # Print estimated cost
            input_cost_usd = input_tokens * 0.005 / 1000
            output_cost_usd = output_tokens * 0.015 / 1000
            total_cost_usd = input_cost_usd + output_cost_usd

            # Convert to AUD using forex-python
            try:
                c = CurrencyRates()
                rate = c.get_rate('USD', 'AUD')
                total_cost_aud = total_cost_usd * rate
            except Exception:
                rate = 1.5
                total_cost_aud = total_cost_usd * rate
                print("Could not fetch live exchange rate. AUD conversion skipped.")

            print(f"Script generated successfully.\nInput Tokens: {input_tokens}, Output Tokens: {output_tokens},\nEstimated Cost: ${total_cost_aud:.4f} AUD ({rate:.2f} rate if available)")
            
            # Log the event
            self.df_log = db_logger.log_event(
                self.df_log,
                account=account,
                topic=topic,
                status="Script Generated",
                notes="Success",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=total_cost_usd,
                estimated_cost_aud=total_cost_aud
            )
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            db_logger.save_log(self.df_log, self.log_path)

            # Extract and return the responsw content
            script_json_raw = response.choices[0].message.content
            script_json = clean_json_output(script_json_raw)
            return script_json

        except Exception as e:
            raise RuntimeError(f"OpenAI API call failed: {e}")

    
    def save_script(self, script_json, topic, output_dir):
        """
        Saves the generated script in JSON to specified output
        """
        output_path = self.project_root / output_dir
        output_path.mkdir(parents=True, exist_ok=True)
        file_path = output_path / f"{topic.replace(' ', '_').lower()}.json"

        with open(file_path, 'w') as f:
            f.write(script_json)
        print(f"Script saved to {file_path}")

        return file_path

#if __name__ == "__main__":
def script_generator(topic, tone, account="default_account"):
    from pathlib import Path
    load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
    api_key = os.getenv("OPENAI_API_KEY")

    # Initialise the generator
    generator = ScriptGenerator(
        api_key=api_key,
        prompt_template_path="data/prompts/prompt_template.txt",
        log_path="data/logs/content_log.csv"
    )

    # Example script generation
    # topic = "Quantum Entanglement"
    # tone = "Humorous"

    # generate and save script
    script_json = generator.generate_script(topic=topic, tone=tone, account="my_test_account")
    file_path = generator.save_script(script_json, topic, output_dir="data/scripts/")
    return file_path