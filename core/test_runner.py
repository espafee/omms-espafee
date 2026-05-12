from django.test.runner import DiscoverRunner


class BackendOnlyDiscoverRunner(DiscoverRunner):
    """Keep default Django discovery inside backend app packages.

    Django's default no-label discovery starts at the current working directory.
    In this repo that can include frontend/E2E tooling, so `manage.py test`
    should behave like `manage.py test apps` unless a caller passes labels.
    """

    default_test_labels = ("apps",)

    def run_tests(self, test_labels, **kwargs):
        labels = test_labels or self.default_test_labels
        return super().run_tests(labels, **kwargs)
