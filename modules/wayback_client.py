"""Wayback Machine Client Module.

Provides integration with the Internet Archive's Wayback Machine API
for retrieving archived versions of URLs and ensuring citation permanence.
"""

import re
import time
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime
from loguru import logger

import requests


@dataclass
class WaybackSnapshot:
    """Metadata for a Wayback Machine snapshot."""
    original_url: str
    archived_url: str
    timestamp: str  # YYYYMMDDHHMMSS format
    status_code: str
    mime_type: str
    
    @property
    def archive_date(self) -> datetime:
        """Parse timestamp into datetime object."""
        try:
            return datetime.strptime(self.timestamp[:14], "%Y%m%d%H%M%S")
        except (ValueError, IndexError):
            return datetime.now()
    
    @property
    def formatted_date(self) -> str:
        """Return human-readable date."""
        return self.archive_date.strftime("%B %d, %Y")
    
    @property
    def year(self) -> str:
        """Extract year from timestamp."""
        return self.timestamp[:4] if len(self.timestamp) >= 4 else ""


class WaybackClient:
    """
    Client for the Internet Archive Wayback Machine API.
    
    API docs: https://archive.org/help/wayback_api.php
    """
    
    AVAILABILITY_API = "https://archive.org/wayback/available"
    CDX_API = "https://web.archive.org/cdx/search/cdx"
    SAVE_API = "https://web.archive.org/save"
    
    def __init__(self, request_delay: float = 1.0):
        """
        Initialize the Wayback client.
        
        Args:
            request_delay: Minimum seconds between requests
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'CitationSculptor/1.8.0 (https://github.com/yourusername/CitationSculptor)'
        })
        self.request_delay = request_delay
        self.last_request_time = 0.0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def get_closest_snapshot(self, url: str, timestamp: str = None) -> Optional[WaybackSnapshot]:
        """
        Get the closest archived snapshot to a given timestamp.
        
        Args:
            url: URL to look up
            timestamp: Optional timestamp (YYYYMMDD or YYYYMMDDHHMMSS), defaults to now
        
        Returns:
            WaybackSnapshot or None if not archived
        """
        self._rate_limit()
        
        try:
            params = {'url': url}
            if timestamp:
                params['timestamp'] = timestamp
            
            response = self.session.get(self.AVAILABILITY_API, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            archived = data.get('archived_snapshots', {}).get('closest')
            
            if archived and archived.get('available'):
                return WaybackSnapshot(
                    original_url=url,
                    archived_url=archived.get('url', ''),
                    timestamp=archived.get('timestamp', ''),
                    status_code=archived.get('status', '200'),
                    mime_type='text/html'
                )
            
            return None
            
        except requests.RequestException as e:
            logger.debug(f"Wayback availability check failed: {e}")
            return None
    
    def get_all_snapshots(
        self, 
        url: str, 
        from_date: str = None,
        to_date: str = None,
        limit: int = 10
    ) -> List[WaybackSnapshot]:
        """
        Get all archived snapshots for a URL within a date range.
        
        Args:
            url: URL to look up
            from_date: Start date (YYYYMMDD)
            to_date: End date (YYYYMMDD)
            limit: Maximum number of results
        
        Returns:
            List of WaybackSnapshot objects (newest first)
        """
        self._rate_limit()
        
        try:
            params = {
                'url': url,
                'output': 'json',
                'limit': limit,
                'fl': 'timestamp,original,statuscode,mimetype',
                'filter': 'statuscode:200',
                'collapse': 'timestamp:8'  # One per day
            }
            
            if from_date:
                params['from'] = from_date
            if to_date:
                params['to'] = to_date
            
            response = self.session.get(self.CDX_API, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            if not data or len(data) < 2:
                return []
            
            # First row is headers
            headers = data[0]
            snapshots = []
            
            for row in data[1:]:
                row_dict = dict(zip(headers, row))
                snapshots.append(WaybackSnapshot(
                    original_url=row_dict.get('original', url),
                    archived_url=f"https://web.archive.org/web/{row_dict.get('timestamp')}/{url}",
                    timestamp=row_dict.get('timestamp', ''),
                    status_code=row_dict.get('statuscode', '200'),
                    mime_type=row_dict.get('mimetype', 'text/html')
                ))
            
            return snapshots
            
        except requests.RequestException as e:
            logger.debug(f"Wayback CDX search failed: {e}")
            return []
    
    def get_archived_url(self, url: str) -> Optional[str]:
        """
        Get the most recent archived URL for a given URL.
        
        This is a convenience method that returns just the archived URL string.
        
        Args:
            url: URL to look up
        
        Returns:
            Archived URL string or None
        """
        snapshot = self.get_closest_snapshot(url)
        return snapshot.archived_url if snapshot else None
    
    def is_archived(self, url: str) -> bool:
        """Check if a URL has been archived."""
        return self.get_closest_snapshot(url) is not None
    
    def format_archived_citation(self, url: str, access_date: str = None) -> Optional[str]:
        """
        Format a URL with its archived version for citation.
        
        Args:
            url: Original URL
            access_date: Optional access date override
        
        Returns:
            Formatted string with original URL, archived URL, and dates
        """
        snapshot = self.get_closest_snapshot(url)
        if not snapshot:
            return None
        
        if not access_date:
            access_date = datetime.now().strftime("%B %d, %Y")
        
        return (
            f"Available from: {url} "
            f"[Archived: {snapshot.archived_url}] "
            f"(Accessed {access_date}; Archived {snapshot.formatted_date})"
        )
    
    def save_page(self, url: str) -> Optional[str]:
        """
        Request the Wayback Machine to save a new snapshot of a URL.
        
        Note: This requires the page to be publicly accessible and may take time.
        
        Args:
            url: URL to archive
        
        Returns:
            Archived URL if successful, None otherwise
        """
        self._rate_limit()
        
        try:
            save_url = f"{self.SAVE_API}/{url}"
            response = self.session.get(save_url, timeout=60, allow_redirects=True)
            
            # The save endpoint redirects to the archived page
            if response.status_code == 200 and 'web.archive.org' in response.url:
                logger.info(f"Successfully archived: {url}")
                return response.url
            
            return None
            
        except requests.RequestException as e:
            logger.debug(f"Wayback save failed: {e}")
            return None
    
    def test_connection(self) -> bool:
        """Test connection to Wayback Machine API."""
        try:
            self._rate_limit()
            response = self.session.get(
                self.AVAILABILITY_API,
                params={'url': 'example.com'},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

