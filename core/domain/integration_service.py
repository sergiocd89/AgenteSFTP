from core import jira
from core.confluence import (
    get_confluence_page_metadata_from_link,
    upload_markdown_to_confluence,
)


def publish_confluence_page(
    title: str,
    markdown_content: str,
    parent_id: str | None = None,
    space_key: str | None = None,
    user: str | None = None,
    api_token: str | None = None,
) -> dict:
    return upload_markdown_to_confluence(
        title=title,
        markdown_content=markdown_content,
        parent_id=parent_id,
        space_key=space_key,
        user=user,
        api_token=api_token,
    )


def resolve_confluence_metadata(page_url: str, user: str, api_token: str) -> dict:
    return get_confluence_page_metadata_from_link(page_url, user, api_token)


def publish_jira_issue(
    base_url: str,
    project_key: str,
    issue_type: str,
    summary: str,
    description_text: str,
    jira_user: str | None = None,
    jira_password: str | None = None,
) -> dict:
    return jira.create_jira_issue(
        base_url=base_url,
        project_key=project_key,
        issue_type=issue_type,
        summary=summary,
        description_text=description_text,
        jira_user=jira_user,
        jira_password=jira_password,
    )
