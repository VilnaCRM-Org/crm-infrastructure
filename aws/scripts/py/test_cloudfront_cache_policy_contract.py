"""Keep CloudFront TTL ownership in the cache policy for both distributions."""

from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[3] / "terraform/app/modules/aws/cloudfront"


class CloudFrontCachePolicyContractTests(unittest.TestCase):
    def test_distributions_do_not_configure_legacy_ttls(self):
        source = (MODULE / "main.tf").read_text()
        self.assertEqual(source.count("default_cache_behavior {"), 2)
        self.assertEqual(
            source.count(
                "cache_policy_id = aws_cloudfront_cache_policy.cloudfront_cache_policy.id"
            ),
            2,
        )
        self.assertNotRegex(source, r"(?m)^\s*(min_ttl|default_ttl|max_ttl)\s*=")

    def test_cache_policy_retains_configured_ttls(self):
        source = (MODULE / "cache_policy.tf").read_text()
        for name in ("min_ttl", "default_ttl", "max_ttl"):
            self.assertRegex(
                source,
                rf"(?m)^\s*{name}\s*=\s*var\.cloudfront_configuration\.{name}\s*$",
            )


if __name__ == "__main__":
    unittest.main()
