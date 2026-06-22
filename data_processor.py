#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Data Processor for ALPHA EDUCATION Dashboard
Извлекает данные из Excel-выгрузки amoCRM и генерирует data.json
в формате, который ожидает dashboard.html (переменная RAW).

Использование:
    pip install pandas openpyxl --break-system-packages
    python3 data_processor.py
"""

import pandas as pd
import json
import os
from datetime import datetime

EXCEL_FILE = 'amocrm_export_leads_2026-06-19.xlsx'
OUTPUT_FILE = 'data.json'


def find_column(df, keywords):
    """Найти столбец по ключевым словам в названии (регистронезависимо)."""
    for col in df.columns:
        low = str(col).lower()
        if any(k in low for k in keywords):
            return col
    return None


def process_data():
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ Файл {EXCEL_FILE} не найден в текущей папке.")
        return False

    df = pd.read_excel(EXCEL_FILE)
    df.columns = df.columns.str.strip()

    # --- определяем ключевые столбцы динамически, а не по индексу ---
    status_col   = find_column(df, ['этап', 'статус']) or df.columns[6]
    manager_col  = find_column(df, ['ответственный', 'менеджер']) or df.columns[5]
    date_col     = find_column(df, ['дата создания', 'создания']) or df.columns[8]
    budget_col   = find_column(df, ['бюджет', 'budget']) or 'Бюджет'
    id_col       = find_column(df, ['id сделки', 'id'])  or df.columns[0]

    for col in [c for c in df.columns if 'дата' in c.lower()]:
        df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)

    # --- фильтр по программам MN / Школа Менеджмента ---
    text_cols = df.select_dtypes(include=['object']).columns
    mask_mn = pd.Series(False, index=df.index)
    mask_school = pd.Series(False, index=df.index)
    for col in text_cols:
        mask_mn |= df[col].astype(str).str.contains(r'\bMN\b|мн\b', case=False, na=False, regex=True)
        mask_school |= df[col].astype(str).str.contains(
            'школа менеджмента|school of management|менеджмент bootcamp', case=False, na=False)

    df_f = df[mask_mn | mask_school].copy()
    df_f['program'] = 'MN'
    df_f.loc[mask_school[df_f.index], 'program'] = 'Школа Менеджмента'

    if df_f.empty:
        print("⚠️  После фильтрации по программам не осталось строк — проверьте ключевые слова.")
        return False

    completed_kw = ['выпускники', 'завершил', 'успешно', 'finished', 'completed', 'оплатившие']
    churn_kw = ['отказ', 'отложили', 'не актуально', 'зона отчуждения', 'lost']

    df_f['status_lower'] = df_f[status_col].astype(str).str.lower()
    df_f['is_completed'] = df_f['status_lower'].str.contains('|'.join(completed_kw), na=False)
    df_f['is_churned'] = df_f['status_lower'].str.contains('|'.join(churn_kw), na=False)
    df_f[budget_col] = pd.to_numeric(df_f[budget_col], errors='coerce').fillna(0)

    # --- помесячная динамика ---
    df_f['month_dt'] = df_f[date_col]
    df_f['month_key'] = df_f['month_dt'].dt.to_period('M')
    monthly = df_f.groupby('month_key').agg(
        total=(id_col, 'count'),
        completed=('is_completed', 'sum'),
        churned=('is_churned', 'sum'),
        budget=(budget_col, 'sum')
    ).reset_index().sort_values('month_key')
    monthly['month'] = monthly['month_key'].dt.strftime('%b %Y')
    monthly['budget'] = (monthly['budget'] / 1e9).round(2)  # в млрд сум
    monthly_records = monthly[['month', 'total', 'completed', 'churned', 'budget']].tail(12).to_dict('records')

    # --- менеджеры, с разбивкой по программам ---
    manager_rows = []
    for mgr, g in df_f.groupby(manager_col):
        total = len(g)
        completed = int(g['is_completed'].sum())
        budget = round(g[budget_col].sum() / 1e9, 1)
        programs = g['program'].value_counts().to_dict()
        manager_rows.append({
            'id': str(mgr).lower().replace(' ', '_'),
            'name': str(mgr),
            'total': total,
            'completed': completed,
            'budget': budget,
            'programs': programs
        })
    manager_rows.sort(key=lambda r: r['completed'], reverse=True)

    # --- причины оттока ---
    churned_df = df_f[df_f['is_churned']]
    churn_counts = churned_df[status_col].value_counts()
    total_churn = churn_counts.sum()
    churn_reasons = [
        {'reason': str(reason), 'pct': round(count / total_churn * 100, 1)}
        for reason, count in churn_counts.items()
    ] if total_churn else []

    # --- распределение по программам (общее) ---
    program_split = (df_f['program'].value_counts(normalize=True) * 100).round(0).to_dict()

    output = {
        'monthly': monthly_records,
        'managers': manager_rows,
        'churnReasons': churn_reasons,
        'programSplit': program_split,
        'lastUpdated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ data.json обновлён: {output['lastUpdated']}")
    print(f"   Лидов в выборке: {len(df_f):,}")
    print(f"   Завершено: {sum(m['completed'] for m in manager_rows):,}")
    print(f"   Менеджеров: {len(manager_rows)}")
    return True


if __name__ == '__main__':
    process_data()
