import pandas as pd
from pathlib import Path
from datetime import datetime

def init_log(filepath):
    """Loads an existing log or creates a new Df with proper columns"""
    if Path(filepath).exists():
        return pd.read_csv(filepath)
    else:
        columns = [
            'timestamp', 'account', 'topic', 'status', 'notes', 'input_tokens',
            'output_tokens', 'total_tokens', 'estimated_cost_usd', 'estimated_cost_aud'
        ]
        return pd.DataFrame(columns=columns)
    
def log_event(df, account, topic, status, notes,
              input_tokens=None, output_tokens=None, 
              total_tokens=None, estimated_cost_usd=None, estimated_cost_aud=None):
    """
    Appends a new row to the log DataFrame.
    """
    new_row = {
        'timestamp': datetime.now().isoformat(),
        'account': account,
        'topic': topic,
        'status': status,
        'notes': notes,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'estimated_cost_usd': estimated_cost_usd,
        'estimated_cost_aud': estimated_cost_aud
    }
    if df.empty:
        df = pd.DataFrame([new_row])
    else:
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return df


def save_log(df, filepath):
    """Saves the log DF to csv"""
    df.to_csv(filepath, index=False)