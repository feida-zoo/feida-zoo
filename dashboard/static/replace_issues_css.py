#!/usr/bin/env python3
"""
批量替换问题管理页暗色 CSS 为亮色
"""
import re

with open('dev_center.css', 'r', encoding='utf-8') as f:
    css = f.read()

# 定义替换规则（精确匹配，避免误伤其他选择器）
replacements = [
    # 容器/头部/工具栏
    ('.issues-container {\n    display: flex;\n    flex-direction: column;\n    width: 100%;\n    background: #1e1e2e;', '.issues-container {\n    display: flex;\n    flex-direction: column;\n    width: 100%;\n    background: white;'),
    ('.issues-header {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 16px 24px;\n    background: #181825;\n    border-bottom: 1px solid #313244;', '.issues-header {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 16px 24px;\n    background: white;\n    border-bottom: 1px solid var(--border-color);'),
    ('.issues-header h2 {\n    margin: 0;\n    color: #cdd6f4;', '.issues-header h2 {\n    margin: 0;\n    color: var(--dark-color);'),
    ('.issues-header h2 i {\n    color: #f9e2af;', '.issues-header h2 i {\n    color: var(--primary-color);'),
    ('.btn-create-issue {\n    background: #a6e3a1;\n    color: #1e1e2e;', '.btn-create-issue {\n    background: var(--primary-color);\n    color: white;'),
    ('.btn-create-issue:hover {\n    background: #b8ebc2;', '.btn-create-issue:hover {\n    background: #2980b9;'),
    ('.issues-toolbar {\n    display: flex;\n    gap: 10px;\n    padding: 12px 24px;\n    background: #181825;\n    border-bottom: 1px solid #313244;', '.issues-toolbar {\n    display: flex;\n    gap: 10px;\n    padding: 12px 24px;\n    background: white;\n    border-bottom: 1px solid var(--border-color);'),
    ('.issues-toolbar select,\n.issues-toolbar input[type="text"] {\n    background: #313244;\n    color: #cdd6f4;\n    border: 1px solid #45475a;', '.issues-toolbar select,\n.issues-toolbar input[type="text"] {\n    background: var(--light-color);\n    color: var(--dark-color);\n    border: 1px solid var(--border-color);'),
    ('.issues-toolbar select:focus,\n.issues-toolbar input[type="text"]:focus {\n    border-color: #89b4fa;', '.issues-toolbar select:focus,\n.issues-toolbar input[type="text"]:focus {\n    border-color: var(--primary-color);'),
    ('.issues-toolbar input[type="text"]::placeholder {\n    color: #585b70;', '.issues-toolbar input[type="text"]::placeholder {\n    color: var(--gray-color);'),
    ('.issues-list {\n    flex: 1;\n    overflow-y: auto;\n    padding: 16px 24px;\n    display: flex;\n    flex-direction: column;\n    gap: 12px;\n}', '.issues-list {\n    flex: 1;\n    overflow-y: auto;\n    padding: 16px 24px;\n    display: flex;\n    flex-direction: column;\n    gap: 12px;\n    background: white;\n}'),
    # 卡片
    ('.issue-card {\n    display: flex;\n    gap: 12px;\n    background: #313244;\n    border: 1px solid #45475a;', '.issue-card {\n    display: flex;\n    gap: 12px;\n    background: var(--light-color);\n    border: 1px solid var(--border-color);'),
    ('.issue-card:hover {\n    background: #3a3a4a;', '.issue-card:hover {\n    background: white;\n    box-shadow: 0 4px 12px rgba(0,0,0,0.08);'),
    ('.issue-card-left {\n    display: flex;\n    flex-direction: column;\n    align-items: center;\n    gap: 6px;\n    min-width: 40px;\n    padding-right: 12px;\n    border-right: 1px solid #45475a;', '.issue-card-left {\n    display: flex;\n    flex-direction: column;\n    align-items: center;\n    gap: 6px;\n    min-width: 40px;\n    padding-right: 12px;\n    border-right: 1px solid var(--border-color);'),
    ('.issue-number {\n    font-size: 0.75rem;\n    font-weight: 700;\n    color: #a6adc8;', '.issue-number {\n    font-size: 0.75rem;\n    font-weight: 700;\n    color: var(--gray-color);'),
    ('.issue-avatar {\n    width: 32px;\n    height: 32px;\n    border-radius: 50%;\n    background: #89b4fa;\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    font-size: 0.85rem;\n    color: #1e1e2e;', '.issue-avatar {\n    width: 32px;\n    height: 32px;\n    border-radius: 50%;\n    background: var(--primary-color);\n    display: flex;\n    align-items: center;\n    justify-content: center;\n    font-size: 0.85rem;\n    color: white;'),
    ('.issue-title {\n    font-weight: 600;\n    font-size: 0.95rem;\n    color: #cdd6f4;', '.issue-title {\n    font-weight: 600;\n    font-size: 0.95rem;\n    color: var(--dark-color);'),
    ('.issue-description {\n    font-size: 0.8rem;\n    color: #a6adc8;', '.issue-description {\n    font-size: 0.8rem;\n    color: var(--gray-color);'),
    ('.issue-meta {\n    display: flex;\n    gap: 12px;\n    font-size: 0.75rem;\n    color: #a6adc8;', '.issue-meta {\n    display: flex;\n    gap: 12px;\n    font-size: 0.75rem;\n    color: var(--gray-color);'),
    ('.issue-meta i {\n    color: #89b4fa;', '.issue-meta i {\n    color: var(--primary-color);'),
    ('.issue-card-actions {\n    display: flex;\n    flex-direction: column;\n    gap: 6px;\n    align-items: flex-end;\n    min-width: 80px;\n    padding-left: 12px;\n    border-left: 1px solid #45475a;', '.issue-card-actions {\n    display: flex;\n    flex-direction: column;\n    gap: 6px;\n    align-items: flex-end;\n    min-width: 80px;\n    padding-left: 12px;\n    border-left: 1px solid var(--border-color);'),
    ('.btn-edit-issue {\n    background: #45475a;\n    color: #cdd6f4;\n    border: none;', '.btn-edit-issue {\n    background: var(--light-color);\n    color: var(--dark-color);\n    border: 1px solid var(--border-color);'),
    ('.btn-edit-issue:hover {\n    background: #585b70;', '.btn-edit-issue:hover {\n    background: var(--border-color);'),
    ('.btn-resolve-issue {\n    background: #a6e3a1;\n    color: #1e1e2e;\n    border: none;', '.btn-resolve-issue {\n    background: var(--success-color);\n    color: white;\n    border: none;'),
    ('.btn-resolve-issue:hover {\n    background: #b8ebc2;', '.btn-resolve-issue:hover {\n    background: #27ae60;'),
    ('.btn-delete-issue {\n    background: #f38ba8;\n    color: #1e1e2e;\n    border: none;', '.btn-delete-issue {\n    background: var(--danger-color);\n    color: white;\n    border: none;'),
    ('.btn-delete-issue:hover {\n    background: #f5a3b8;', '.btn-delete-issue:hover {\n    background: #c0392b;'),
    ('.empty-state {\n    text-align: center;\n    padding: 40px 20px;\n    color: #585b70;', '.empty-state {\n    text-align: center;\n    padding: 40px 20px;\n    color: var(--gray-color);'),
    ('.empty-state i {\n    font-size: 2.5rem;\n    margin-bottom: 12px;\n    color: #585b70;', '.empty-state i {\n    font-size: 2.5rem;\n    margin-bottom: 12px;\n    color: var(--gray-color);'),
    # Modal
    ('.issue-modal-content {\n    background: #1e1e2e;', '.issue-modal-content {\n    background: white;'),
    ('.issue-modal-header {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 16px 24px;\n    border-bottom: 1px solid #313244;', '.issue-modal-header {\n    display: flex;\n    justify-content: space-between;\n    align-items: center;\n    padding: 16px 24px;\n    border-bottom: 1px solid var(--border-color);'),
    ('.issue-modal-header h3 {\n    margin: 0;\n    color: #cdd6f4;', '.issue-modal-header h3 {\n    margin: 0;\n    color: var(--dark-color);'),
    ('.btn-close-modal {\n    background: none;\n    border: none;\n    color: #a6adc8;', '.btn-close-modal {\n    background: none;\n    border: none;\n    color: var(--gray-color);'),
    ('.btn-close-modal:hover {\n    background: #313244;', '.btn-close-modal:hover {\n    background: var(--light-color);'),
    ('.issue-modal-body label {\n    display: block;\n    margin-bottom: 6px;\n    font-weight: 500;\n    font-size: 0.9rem;\n    color: #a6adc8;', '.issue-modal-body label {\n    display: block;\n    margin-bottom: 6px;\n    font-weight: 500;\n    font-size: 0.9rem;\n    color: var(--dark-color);'),
    ('.issue-modal-body input[type="text"],\n.issue-modal-body select,\n.issue-modal-body textarea {\n    width: 100%;\n    padding: 10px 12px;\n    border: 1px solid #45475a;\n    border-radius: 6px;\n    font-size: 0.9rem;\n    font-family: inherit;\n    color: #cdd6f4;\n    background: #313244;', '.issue-modal-body input[type="text"],\n.issue-modal-body select,\n.issue-modal-body textarea {\n    width: 100%;\n    padding: 10px 12px;\n    border: 1px solid var(--border-color);\n    border-radius: 6px;\n    font-size: 0.9rem;\n    font-family: inherit;\n    color: var(--dark-color);\n    background: var(--light-color);'),
    ('.issue-modal-body input:focus,\n.issue-modal-body select:focus,\n.issue-modal-body textarea:focus {\n    border-color: #89b4fa;', '.issue-modal-body input:focus,\n.issue-modal-body select:focus,\n.issue-modal-body textarea:focus {\n    border-color: var(--primary-color);'),
    ('.issue-modal-footer {\n    display: flex;\n    justify-content: flex-end;\n    gap: 10px;\n    padding: 16px 24px;\n    border-top: 1px solid #313244;', '.issue-modal-footer {\n    display: flex;\n    justify-content: flex-end;\n    gap: 10px;\n    padding: 16px 24px;\n    border-top: 1px solid var(--border-color);'),
    ('.btn-save-issue {\n    background: #a6e3a1;\n    color: #1e1e2e;\n    border: none;', '.btn-save-issue {\n    background: var(--primary-color);\n    color: white;\n    border: none;'),
    ('.btn-save-issue:hover {\n    background: #b8ebc2;', '.btn-save-issue:hover {\n    background: #2980b9;'),
    ('.btn-cancel-issue {\n    background: #45475a;\n    color: #cdd6f4;\n    border: none;', '.btn-cancel-issue {\n    background: var(--light-color);\n    color: var(--dark-color);\n    border: 1px solid var(--border-color);'),
    ('.btn-cancel-issue:hover {\n    background: #585b70;', '.btn-cancel-issue:hover {\n    background: var(--border-color);'),
    ('.btn-confirm-delete {\n    background: #f38ba8;\n    color: #1e1e2e;\n    border: none;', '.btn-confirm-delete {\n    background: var(--danger-color);\n    color: white;\n    border: none;'),
    ('.btn-confirm-delete:hover {\n    background: #f5a3b8;', '.btn-confirm-delete:hover {\n    background: #c0392b;'),
]

count = 0
for old, new in replacements:
    if old in css:
        css = css.replace(old, new)
        count += 1
    else:
        print(f"WARNING: not found: {old[:60]}...")

with open('dev_center.css', 'w', encoding='utf-8') as f:
    f.write(css)

print(f"Replaced {count}/{len(replacements)} patterns")
