from django.core.management.base import BaseCommand
from django.urls import get_resolver
from django.urls.resolvers import URLResolver


class Command(BaseCommand):
    help = "List all URL patterns in the project"

    def print_level(self, url_patterns, indent_str=""):
        for pattern in sorted(url_patterns, key=lambda pattern: str(pattern.pattern)):
            pattern_str = str(pattern.pattern)
            has_path = pattern_str not in ("", "^")
            if isinstance(pattern, URLResolver):
                if has_path:
                    self.stdout.write(
                        f"{indent_str}{pattern_str} [namespace='{pattern.namespace}']"
                    )

                self.print_level(
                    pattern.url_patterns,
                    " " * (len(pattern_str) + len(indent_str))
                    if has_path
                    else indent_str,
                )
            else:
                pattern_str = "/" if not has_path else pattern_str
                self.stdout.write(f"{indent_str}{pattern_str} [name='{pattern.name}']")

    def handle(self, *args, **kwargs):  # noqa: ARG002
        url_patterns = get_resolver().url_patterns
        self.stdout.write("List of URL patterns:")

        self.print_level(url_patterns)
