"""Book Metadata Client Module.

Provides integration with Google Books and OpenLibrary APIs for ISBN lookup.
"""

import re
import time
from dataclasses import dataclass
from typing import Optional, List
from loguru import logger

import requests


@dataclass
class BookMetadata:
    """Metadata for a book."""
    isbn: str
    title: str
    authors: List[str]
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    page_count: Optional[int] = None
    description: Optional[str] = None
    categories: Optional[List[str]] = None
    language: Optional[str] = None
    edition: Optional[str] = None
    # Identifiers
    isbn_10: Optional[str] = None
    isbn_13: Optional[str] = None
    oclc: Optional[str] = None
    lccn: Optional[str] = None
    # Links
    info_link: Optional[str] = None
    preview_link: Optional[str] = None
    thumbnail: Optional[str] = None
    # Source
    source: str = "unknown"  # 'google_books' or 'openlibrary'
    
    def get_first_author_label(self) -> str:
        """Get label from first author's surname + first initial."""
        if not self.authors:
            return "Unknown"
        first = self.authors[0]
        parts = first.split()
        if len(parts) >= 2:
            surname = parts[-1]
            initial = parts[0][0] if parts[0] else ""
            return f"{surname}{initial}"
        return first[:10] if first else "Unknown"
    
    @property
    def year(self) -> str:
        """Extract year from published date."""
        if self.published_date:
            # Handle various formats: "2023", "2023-01", "2023-01-15", "January 2023"
            match = re.search(r'\b(19|20)\d{2}\b', self.published_date)
            if match:
                return match.group(0)
        return ""
    
    @property
    def display_isbn(self) -> str:
        """Return ISBN-13 if available, else ISBN-10."""
        return self.isbn_13 or self.isbn_10 or self.isbn


class BookClient:
    """
    Client for book metadata lookup via Google Books and OpenLibrary APIs.
    """
    
    GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
    OPENLIBRARY_URL = "https://openlibrary.org/api/books"
    OPENLIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
    
    # ISBN patterns
    ISBN_10_PATTERN = re.compile(r'^(\d{9}[\dXx])$')
    ISBN_13_PATTERN = re.compile(r'^(97[89]\d{10})$')
    ISBN_LOOSE_PATTERN = re.compile(r'^[\d\-\sXx]{10,17}$')
    
    def __init__(self, google_api_key: Optional[str] = None, request_delay: float = 0.5):
        """
        Initialize the book client.
        
        Args:
            google_api_key: Optional Google Books API key (increases rate limits)
            request_delay: Minimum seconds between requests
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CitationSculptor/1.6.0 (https://github.com/yourusername/CitationSculptor)'
        })
        self.google_api_key = google_api_key
        self.request_delay = request_delay
        self.last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def is_isbn(self, identifier: str) -> bool:
        """Check if a string looks like an ISBN."""
        cleaned = self._clean_isbn(identifier)
        return bool(self.ISBN_10_PATTERN.match(cleaned) or self.ISBN_13_PATTERN.match(cleaned))
    
    def _clean_isbn(self, isbn: str) -> str:
        """Remove hyphens, spaces and normalize ISBN."""
        return re.sub(r'[-\s]', '', isbn.strip()).upper()
    
    def _validate_isbn_10(self, isbn: str) -> bool:
        """Validate ISBN-10 checksum."""
        if len(isbn) != 10:
            return False
        try:
            total = sum(int(isbn[i]) * (10 - i) for i in range(9))
            check = isbn[9]
            check_value = 10 if check == 'X' else int(check)
            return (total + check_value) % 11 == 0
        except (ValueError, IndexError):
            return False
    
    def _validate_isbn_13(self, isbn: str) -> bool:
        """Validate ISBN-13 checksum."""
        if len(isbn) != 13:
            return False
        try:
            total = sum(int(isbn[i]) * (1 if i % 2 == 0 else 3) for i in range(12))
            check = (10 - (total % 10)) % 10
            return check == int(isbn[12])
        except (ValueError, IndexError):
            return False
    
    def fetch_by_isbn(self, isbn: str) -> Optional[BookMetadata]:
        """
        Fetch book metadata by ISBN.
        
        Tries Google Books first, then falls back to OpenLibrary.
        
        Args:
            isbn: ISBN-10 or ISBN-13 (with or without hyphens)
        
        Returns:
            BookMetadata object or None if not found
        """
        cleaned_isbn = self._clean_isbn(isbn)
        
        # Try Google Books first
        result = self._fetch_from_google_books(cleaned_isbn)
        if result:
            return result
        
        # Fall back to OpenLibrary
        result = self._fetch_from_openlibrary(cleaned_isbn)
        if result:
            return result
        
        logger.warning(f"Book not found for ISBN: {isbn}")
        return None
    
    def search(self, query: str, max_results: int = 10) -> List[BookMetadata]:
        """
        Search for books by title, author, or general query.
        
        Args:
            query: Search query
            max_results: Maximum number of results
        
        Returns:
            List of BookMetadata objects
        """
        results = []
        
        # Try Google Books search
        google_results = self._search_google_books(query, max_results)
        results.extend(google_results)
        
        # If not enough results, try OpenLibrary
        if len(results) < max_results:
            ol_results = self._search_openlibrary(query, max_results - len(results))
            # Avoid duplicates based on ISBN
            existing_isbns = {r.display_isbn for r in results if r.display_isbn}
            for book in ol_results:
                if book.display_isbn and book.display_isbn not in existing_isbns:
                    results.append(book)
        
        return results[:max_results]
    
    def _fetch_from_google_books(self, isbn: str) -> Optional[BookMetadata]:
        """Fetch book from Google Books API."""
        self._rate_limit()
        
        try:
            params = {'q': f'isbn:{isbn}'}
            if self.google_api_key:
                params['key'] = self.google_api_key
            
            response = self.session.get(self.GOOGLE_BOOKS_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if data.get('totalItems', 0) == 0 or not data.get('items'):
                return None
            
            return self._parse_google_books_item(data['items'][0], isbn)
            
        except requests.RequestException as e:
            logger.debug(f"Google Books lookup failed: {e}")
            return None
    
    def _search_google_books(self, query: str, max_results: int) -> List[BookMetadata]:
        """Search Google Books API."""
        self._rate_limit()
        
        try:
            params = {
                'q': query,
                'maxResults': min(max_results, 40),
                'printType': 'books'
            }
            if self.google_api_key:
                params['key'] = self.google_api_key
            
            response = self.session.get(self.GOOGLE_BOOKS_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('items', []):
                metadata = self._parse_google_books_item(item)
                if metadata:
                    results.append(metadata)
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"Google Books search failed: {e}")
            return []
    
    def _parse_google_books_item(self, item: dict, original_isbn: str = "") -> Optional[BookMetadata]:
        """Parse Google Books API response item."""
        try:
            volume_info = item.get('volumeInfo', {})
            
            title = volume_info.get('title', '')
            if not title:
                return None
            
            # Extract identifiers
            isbn_10 = isbn_13 = None
            for ident in volume_info.get('industryIdentifiers', []):
                if ident.get('type') == 'ISBN_10':
                    isbn_10 = ident.get('identifier')
                elif ident.get('type') == 'ISBN_13':
                    isbn_13 = ident.get('identifier')
            
            # Use original ISBN if no identifiers found
            primary_isbn = isbn_13 or isbn_10 or original_isbn
            
            return BookMetadata(
                isbn=primary_isbn,
                title=title,
                authors=volume_info.get('authors', []),
                publisher=volume_info.get('publisher'),
                published_date=volume_info.get('publishedDate'),
                page_count=volume_info.get('pageCount'),
                description=volume_info.get('description'),
                categories=volume_info.get('categories'),
                language=volume_info.get('language'),
                isbn_10=isbn_10,
                isbn_13=isbn_13,
                info_link=volume_info.get('infoLink'),
                preview_link=volume_info.get('previewLink'),
                thumbnail=volume_info.get('imageLinks', {}).get('thumbnail'),
                source='google_books'
            )
            
        except Exception as e:
            logger.error(f"Failed to parse Google Books item: {e}")
            return None
    
    def _fetch_from_openlibrary(self, isbn: str) -> Optional[BookMetadata]:
        """Fetch book from OpenLibrary API."""
        self._rate_limit()
        
        try:
            params = {
                'bibkeys': f'ISBN:{isbn}',
                'format': 'json',
                'jscmd': 'data'
            }
            
            response = self.session.get(self.OPENLIBRARY_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            key = f'ISBN:{isbn}'
            
            if key not in data:
                return None
            
            return self._parse_openlibrary_item(data[key], isbn)
            
        except requests.RequestException as e:
            logger.debug(f"OpenLibrary lookup failed: {e}")
            return None
    
    def _search_openlibrary(self, query: str, max_results: int) -> List[BookMetadata]:
        """Search OpenLibrary."""
        self._rate_limit()
        
        try:
            params = {
                'q': query,
                'limit': min(max_results, 100),
                'mode': 'everything'
            }
            
            response = self.session.get(self.OPENLIBRARY_SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for doc in data.get('docs', []):
                # Get ISBN from search result
                isbns = doc.get('isbn', [])
                primary_isbn = isbns[0] if isbns else ""
                
                if not doc.get('title'):
                    continue
                
                isbn_13 = None
                isbn_10 = None
                for i in isbns:
                    cleaned = self._clean_isbn(i)
                    if len(cleaned) == 13:
                        isbn_13 = cleaned
                    elif len(cleaned) == 10:
                        isbn_10 = cleaned
                
                results.append(BookMetadata(
                    isbn=isbn_13 or isbn_10 or primary_isbn,
                    title=doc.get('title', ''),
                    authors=doc.get('author_name', []),
                    publisher=doc.get('publisher', [None])[0] if doc.get('publisher') else None,
                    published_date=str(doc.get('first_publish_year', '')) if doc.get('first_publish_year') else None,
                    page_count=doc.get('number_of_pages_median'),
                    isbn_10=isbn_10,
                    isbn_13=isbn_13,
                    oclc=doc.get('oclc', [None])[0] if doc.get('oclc') else None,
                    lccn=doc.get('lccn', [None])[0] if doc.get('lccn') else None,
                    source='openlibrary'
                ))
            
            return results
            
        except requests.RequestException as e:
            logger.debug(f"OpenLibrary search failed: {e}")
            return []
    
    def _parse_openlibrary_item(self, item: dict, isbn: str) -> Optional[BookMetadata]:
        """Parse OpenLibrary API response item."""
        try:
            title = item.get('title', '')
            if not title:
                return None
            
            # Authors
            authors = []
            for author in item.get('authors', []):
                if isinstance(author, dict) and author.get('name'):
                    authors.append(author['name'])
            
            # Publishers
            publishers = item.get('publishers', [])
            publisher = publishers[0].get('name') if publishers and isinstance(publishers[0], dict) else None
            
            # Identifiers
            identifiers = item.get('identifiers', {})
            isbn_10 = identifiers.get('isbn_10', [None])[0] if identifiers.get('isbn_10') else None
            isbn_13 = identifiers.get('isbn_13', [None])[0] if identifiers.get('isbn_13') else None
            oclc = identifiers.get('oclc', [None])[0] if identifiers.get('oclc') else None
            lccn = identifiers.get('lccn', [None])[0] if identifiers.get('lccn') else None
            
            return BookMetadata(
                isbn=isbn_13 or isbn_10 or isbn,
                title=title,
                authors=authors,
                publisher=publisher,
                published_date=item.get('publish_date'),
                page_count=item.get('number_of_pages'),
                isbn_10=isbn_10,
                isbn_13=isbn_13,
                oclc=oclc,
                lccn=lccn,
                info_link=item.get('url'),
                thumbnail=item.get('cover', {}).get('medium'),
                source='openlibrary'
            )
            
        except Exception as e:
            logger.error(f"Failed to parse OpenLibrary item: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to Google Books API."""
        try:
            self._rate_limit()
            params = {'q': 'test', 'maxResults': 1}
            if self.google_api_key:
                params['key'] = self.google_api_key
            response = self.session.get(self.GOOGLE_BOOKS_URL, params=params, timeout=10)
            return response.status_code == 200
        except Exception:
            return False

