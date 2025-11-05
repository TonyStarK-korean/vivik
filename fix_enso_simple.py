# -*- coding: utf-8 -*-
"""
ENSO Position Fix Tool - Simple Version
"""

import json
import os
from datetime import datetime, timezone, timedelta

def fix_enso_position():
    """Fix ENSO position DCA duplication issue"""
    
    positions_file = "dca_positions.json"
    backup_file = "dca_positions_backup_before_enso_fix.json"
    
    if not os.path.exists(positions_file):
        print("dca_positions.json file not found.")
        return
    
    try:
        # Create backup
        with open(positions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Backup created: {backup_file}")
        
        # Fix ENSO position
        if "ENSO/USDT:USDT" in data:
            enso_position = data["ENSO/USDT:USDT"]
            
            print("=== ENSO Position Before Fix ===")
            print(f"Total quantity: {enso_position['total_quantity']}")
            print(f"Average price: {enso_position['average_price']}")
            print(f"Total notional: {enso_position['total_notional']}")
            print(f"Entries count: {len(enso_position['entries'])}")
            
            # Find initial entry
            original_entries = enso_position['entries']
            initial_entry = None
            
            for entry in original_entries:
                if entry['stage'] == 'initial':
                    initial_entry = entry
                    break
            
            if initial_entry:
                # Keep only initial entry, remove DCA entries
                enso_position['entries'] = [initial_entry]
                enso_position['current_stage'] = 'initial'
                enso_position['average_price'] = initial_entry['entry_price']
                enso_position['total_quantity'] = initial_entry['quantity']
                enso_position['total_notional'] = initial_entry['notional']
                enso_position['last_update'] = datetime.now(timezone(timedelta(hours=9))).isoformat()
                
                print("\n=== ENSO Position After Fix ===")
                print(f"Total quantity: {enso_position['total_quantity']}")
                print(f"Average price: {enso_position['average_price']}")
                print(f"Total notional: {enso_position['total_notional']}")
                print(f"Entries count: {len(enso_position['entries'])}")
                print(f"Entry price: {initial_entry['entry_price']}")
                
                # Save fixed data
                with open(positions_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                print("ENSO position fix completed")
                
                # Calculate current P&L (using current price $1.32)
                current_price = 1.32
                profit_pct = (current_price - initial_entry['entry_price']) / initial_entry['entry_price'] * 100
                print(f"\nCurrent price ${current_price:.3f} P&L: {profit_pct:.2f}%")
                
            else:
                print("Initial entry not found.")
        else:
            print("ENSO position not found.")
            
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    fix_enso_position()