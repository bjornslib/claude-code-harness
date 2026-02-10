"""Unit tests for VectorDB custom exceptions."""

from __future__ import annotations

import pytest

from zerorepo.vectordb.exceptions import (
    CollectionError,
    EmbeddingError,
    StoreNotInitializedError,
    VectorStoreError,
)


class TestVectorStoreError:
    """Tests for the base VectorStoreError."""

    def test_is_exception_subclass(self) -> None:
        assert issubclass(VectorStoreError, Exception)

    def test_instantiate_with_message(self) -> None:
        err = VectorStoreError("something failed")
        assert str(err) == "something failed"

    def test_instantiate_no_message(self) -> None:
        err = VectorStoreError()
        assert str(err) == ""

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(VectorStoreError):
            raise VectorStoreError("test")


class TestStoreNotInitializedError:
    """Tests for StoreNotInitializedError."""

    def test_is_vector_store_error(self) -> None:
        assert issubclass(StoreNotInitializedError, VectorStoreError)

    def test_is_exception(self) -> None:
        assert issubclass(StoreNotInitializedError, Exception)

    def test_message_preserved(self) -> None:
        err = StoreNotInitializedError("not initialized")
        assert "not initialized" in str(err)

    def test_caught_as_base(self) -> None:
        with pytest.raises(VectorStoreError):
            raise StoreNotInitializedError("init first")


class TestEmbeddingError:
    """Tests for EmbeddingError."""

    def test_is_vector_store_error(self) -> None:
        assert issubclass(EmbeddingError, VectorStoreError)

    def test_message_preserved(self) -> None:
        err = EmbeddingError("model not found")
        assert "model not found" in str(err)

    def test_caught_as_base(self) -> None:
        with pytest.raises(VectorStoreError):
            raise EmbeddingError("failed")


class TestCollectionError:
    """Tests for CollectionError."""

    def test_is_vector_store_error(self) -> None:
        assert issubclass(CollectionError, VectorStoreError)

    def test_message_preserved(self) -> None:
        err = CollectionError("query failed")
        assert "query failed" in str(err)

    def test_caught_as_base(self) -> None:
        with pytest.raises(VectorStoreError):
            raise CollectionError("bad collection")


class TestExceptionHierarchy:
    """Tests verifying the complete exception hierarchy."""

    def test_all_subclass_base(self) -> None:
        for cls in [StoreNotInitializedError, EmbeddingError, CollectionError]:
            assert issubclass(cls, VectorStoreError)

    def test_all_subclass_exception(self) -> None:
        for cls in [VectorStoreError, StoreNotInitializedError, EmbeddingError, CollectionError]:
            assert issubclass(cls, Exception)

    def test_exceptions_are_distinct(self) -> None:
        with pytest.raises(StoreNotInitializedError):
            raise StoreNotInitializedError("a")
        with pytest.raises(EmbeddingError):
            raise EmbeddingError("b")
        with pytest.raises(CollectionError):
            raise CollectionError("c")
