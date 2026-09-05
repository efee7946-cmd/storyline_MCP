#!/usr/bin/env python
"""Test and display the production logging system."""

import sys
from pathlib import Path

# Add panel to path
panel_dir = Path(__file__).parent
sys.path.insert(0, str(panel_dir))

from production import ProductionLog, format_entry

def main():
    log = ProductionLog()
    entries = log.latest(100)
    
    print("=" * 70)
    print("PRODUCTION LOG — Üretim Günlüğü")
    print("=" * 70)
    print(f"Toplam kayıt: {len(entries)}\n")
    
    if entries:
        print("Son 10 kayıt (en yeni ilk):")
        print("-" * 70)
        for entry in reversed(entries[-10:]):
            print(format_entry(entry))
        print("-" * 70)
        
        # Statistics
        summary = log.summary()
        print(f"\n📊 İstatistikler:")
        print(f"  Başarılı: {summary.get('success_count', 0)}/{summary.get('entries', 0)}")
        print(f"  Başarı %: {summary.get('success_pct', 0)}%")
        print(f"  Sorun olanlar: {summary.get('with_problems', 0)}")
        
        if summary.get('recent_problems'):
            print(f"\n⚠️ Son Sorunlar:")
            for i, problems in enumerate(summary['recent_problems'][-3:], 1):
                for p in problems[:2]:
                    print(f"  {i}. {p}")
    else:
        print("Henüz günlük kaydı yok.")
    
    print("\n📁 Günlük dosyası:")
    print(f"  {log.log_path}")

if __name__ == "__main__":
    main()
