#!/usr/bin/env python3
# Test script for search_by_text

from app import create_app
from flask import current_app, g
from lib.load_config import load_config_from_file
from lib.database_tools import DatabaseTools

config = load_config_from_file()
app = create_app(connection_config=config[1]["database_config"])

with app.app_context():
    # Initialize database tools and attach to Flask g object
    db_config = config[1]["database_config"]
    g.db_tools = DatabaseTools(db_config)
    
    from app.controllers.search_controller import SearchController
    
    print("Testing search_by_text with query 'test'...")
    success, message, results = SearchController.search_by_text('test')
    
    print(f"Success: {success}")
    print(f"Message: {message}")
    print(f"Results count: {len(results) if results else 0}")
    
    if results:
        print("\nFirst few results:")
        for i, result in enumerate(results[:3]):
            print(f"Result {i+1}:")
            print(f"  Image ID: {result.get('image_id')}")
            print(f"  Domain: {result.get('domain')}")
            print(f"  Has image data: {'Yes' if result.get('image_data') else 'No'}")
            print(f"  Use default image: {result.get('use_default_image', True)}")
            print(f"  Image error: {result.get('image_error')}")
            print()
    
    # Clean up - close database connection
    if hasattr(g, 'db_tools'):
        try:
            g.db_tools.releaseConnection(g.db_tools._connection, None)
        except:
            pass
    
    print("Test completed.") 