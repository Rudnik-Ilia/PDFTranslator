def should_retry(errors: list[str], retry_count: int, max_attempts: int) -> bool:
    if not errors:
        return False
    return retry_count < max_attempts - 1


def retry_reason(errors: list[str]) -> str:
    return ";".join(errors) if errors else "unknown"
