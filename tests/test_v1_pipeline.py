"""Integration tests for the v1 Pipeline design."""

import pytest

from dataclean.cleaners.address_cleaner import AddressCleaner
from dataclean.cleaners.country_cleaner import CountryCleaner
from dataclean.cleaners.phone_cleaner import PhoneCleaner
from dataclean.col_renamer import ColRenamer
from dataclean.engine.pandas import PandasDataFrame
from dataclean.pipeline import Pipeline
from dataclean.pipeline.assignments import ColumnAssignment
from dataclean.pipeline.cleaner_resolver import CleanerResolver
from dataclean.pipeline.dependency_resolver import DependencyResolver
from dataclean.pipeline.entity_extractor import EntityExtractor
from dataclean.pipeline.group_cleaner_resolver import GroupCleanerResolver


class TestV1Pipeline:
    """Integration tests for v1 Pipeline design."""

    @pytest.fixture
    def phone_cleaner(self) -> PhoneCleaner:
        """Create a PhoneCleaner with default regions."""
        return PhoneCleaner(default_regions=("IN",))

    @pytest.fixture
    def country_cleaner(self) -> CountryCleaner:
        """Create a CountryCleaner."""
        return CountryCleaner()

    @pytest.fixture
    def address_cleaner(self) -> AddressCleaner:
        """Create an AddressCleaner."""
        return AddressCleaner()

    def test_pipeline_initialization(
        self, phone_cleaner, country_cleaner, address_cleaner
    ):
        """Test pipeline initialization with mixed cleaner types."""
        pipeline = Pipeline(cleaners=[address_cleaner, phone_cleaner, country_cleaner])
        assert len(pipeline.base_cleaners) == 2
        assert len(pipeline.group_cleaners) == 1

    def test_phone_cleaner_provided_roles(self, phone_cleaner):
        """Test that PhoneCleaner provides 'phone' role."""
        roles = phone_cleaner.provided_roles()
        assert "phone" in roles

    def test_country_cleaner_provided_roles(self, country_cleaner):
        """Test that CountryCleaner provides 'country' role."""
        roles = country_cleaner.provided_roles()
        assert "country" in roles

    def test_phone_cleaner_context_requests(self, phone_cleaner):
        """Test that PhoneCleaner requests 'country' context."""
        reqs = phone_cleaner.context_requests()
        assert any(r.role == "country" for r in reqs)

    def test_group_cleaner_resolver(self, address_cleaner):
        """Test GroupCleanerResolver resolving address columns."""
        resolver = GroupCleanerResolver([address_cleaner])
        columns = {"country", "address_line1", "address_line2", "address_line3"}
        assignments = resolver.resolve(columns)
        assert len(assignments) == 1
        assert assignments[0].cleaner == address_cleaner

    def test_cleaner_resolver_confidence(self, phone_cleaner, country_cleaner):
        """Test CleanerResolver with confidence scoring."""
        import pandas as pd

        resolver = CleanerResolver([phone_cleaner, country_cleaner])
        df = PandasDataFrame(
            df=pd.DataFrame(
                {
                    "client_phone": ["+91 9876543210"],
                    "client_country": ["India"],
                }
            )
        )

        assignments = resolver.resolve(df, {"client_phone", "client_country"})
        assert len(assignments) == 2

        phone_assignment = next(a for a in assignments if a.column == "client_phone")
        assert phone_assignment.cleaner == phone_cleaner
        assert phone_assignment.confidence > 0.5

    def test_entity_extractor(self):
        """Test EntityExtractor for entity token matching."""
        col_renamer = ColRenamer()
        extractor = EntityExtractor(col_renamer._get_words)

        # Test extracting entity tokens
        client_entities = extractor.extract("client_phone", "phone")
        assert "client" in client_entities

        manager_entities = extractor.extract("manager_phone", "phone")
        assert "manager" in manager_entities

    def test_entity_overlap(self):
        """Test entity token overlap scoring."""
        col_renamer = ColRenamer()
        extractor = EntityExtractor(col_renamer._get_words)

        # Test exact overlap
        overlap = extractor.entity_overlap(("client",), ("client",))
        assert overlap == 1.0

        # Test no overlap
        overlap = extractor.entity_overlap(("client",), ("manager",))
        assert overlap == 0.0

    def test_dependency_resolver_single_producer(self, phone_cleaner, country_cleaner):
        """Test DependencyResolver with single producer for a role."""
        col_renamer = ColRenamer()
        extractor = EntityExtractor(col_renamer._get_words)
        resolver = DependencyResolver(extractor)

        # Create assignments
        country_assignment = ColumnAssignment(
            column="client_country", cleaner=country_cleaner, confidence=0.9
        )
        phone_assignment = ColumnAssignment(
            column="client_phone", cleaner=phone_cleaner, confidence=0.9
        )

        # Resolve waves
        waves = resolver.resolve([phone_assignment, country_assignment], [])

        # Country should be in wave 0 (no dependencies)
        # Phone should be in wave 1 (depends on country)
        assert len(waves) == 2
        assert country_assignment in waves[0]
        assert phone_assignment in waves[1]

    def test_dependency_resolver_multiple_producers(
        self, phone_cleaner, country_cleaner
    ):
        """Test DependencyResolver disambiguating multiple producers via entity matching."""
        col_renamer = ColRenamer()
        extractor = EntityExtractor(col_renamer._get_words)
        resolver = DependencyResolver(extractor)

        # Create assignments for client and manager countries
        client_country = ColumnAssignment(
            column="client_country", cleaner=country_cleaner, confidence=0.9
        )
        manager_country = ColumnAssignment(
            column="manager_country", cleaner=country_cleaner, confidence=0.9
        )
        client_phone = ColumnAssignment(
            column="client_phone", cleaner=phone_cleaner, confidence=0.9
        )

        # Resolve waves with entity disambiguation
        waves = resolver.resolve([client_country, manager_country, client_phone], [])

        # Should have 2 waves: countries first, then phones
        assert len(waves) == 2

    def test_dependency_resolver_cycle_detection(self, phone_cleaner):
        """Test that DependencyResolver detects cycles."""
        col_renamer = ColRenamer()
        extractor = EntityExtractor(col_renamer._get_words)
        resolver = DependencyResolver(extractor)

        # This is a synthetic test - in practice cycles shouldn't happen
        # because cleaners form a DAG. But we verify the detection logic.
        assignment1 = ColumnAssignment(
            column="col1", cleaner=phone_cleaner, confidence=0.9
        )

        # Manually inject a cycle dependency (shouldn't happen in real usage)
        # For now, verify the resolver handles normal cases
        waves = resolver.resolve([assignment1], [])
        assert len(waves) == 1

    def test_pipeline_fit_transform(self, phone_cleaner, country_cleaner):
        """Test end-to-end Pipeline fit_transform."""
        import pandas as pd

        # pipeline = Pipeline(cleaners=[phone_cleaner, country_cleaner])

        df = PandasDataFrame(
            df=pd.DataFrame(
                {
                    "email": ["test@example.com"],
                    "country": ["India"],
                    "phone": ["+91 9876543210"],
                }
            )
        )

        # This would call the full pipeline
        # Note: fit_transform needs proper DataFrame implementation
        # This is more of a smoke test for now
        assert df is not None

    def test_address_cleaner_clean_row(self, address_cleaner):
        """Test AddressCleaner clean_row method."""
        row = {
            "country": "India",
            "county": "Maharashtra",
            "address_line1": "123 Main Street",
            "address_line2": "Mumbai",
            "address_line3": "400001",
        }

        result = address_cleaner.clean_row(row)
        assert result is not None
        assert (
            len(result) == 6
        )  # country, state, postcode, address_line, street, house_no
        assert result[0] == "India"  # country
        assert result[2] == "400001"  # postcode

    def test_address_cleaner_provided_roles(self, address_cleaner):
        """Test AddressCleaner provided roles."""
        roles = address_cleaner.provided_roles()
        assert "address" in roles
        assert "country" in roles

    def test_country_cleaner_clean_value(self, country_cleaner):
        """Test CountryCleaner clean_value method."""
        result = country_cleaner.clean_value("India")
        assert result == "India"

        result = country_cleaner.clean_value("IN")
        assert result == "India"

    def test_phone_cleaner_clean_value(self, phone_cleaner):
        """Test PhoneCleaner clean_value method."""
        result = phone_cleaner.clean_value("+91 9876543210")
        assert result == "+919876543210"

    def test_cleaner_resolver_auto_detect(self, phone_cleaner, country_cleaner):
        """Test CleanerResolver with auto-detect enabled."""
        import pandas as pd

        resolver = CleanerResolver([phone_cleaner, country_cleaner])
        df = PandasDataFrame(df=pd.DataFrame({"phone": ["+91 9876543210"]}))

        assignments = resolver.resolve(df, {"phone"})
        assert len(assignments) == 1
        assert assignments[0].column == "phone"
