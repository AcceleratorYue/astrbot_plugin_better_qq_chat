"""撤回规则：quoted 消息与权限判断。"""

from __future__ import annotations


def can_recall_quoted(
    *,
    quoted_sender_id: str,
    self_id: str,
    allow_others: bool,
    requester_is_manager: bool,
) -> tuple[bool, str]:
    """判断当前请求者能否撤回被引用的消息。"""
    if not quoted_sender_id:
        return False, "无法确定被引用消息的作者。"
    if self_id and quoted_sender_id == self_id:
        return True, ""
    if not allow_others:
        return False, "只能撤回机器人自己发出的消息。"
    if not requester_is_manager:
        return False, "撤回他人消息需要管理员或群管理员权限。"
    return True, ""
