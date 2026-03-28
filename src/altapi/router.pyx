# cython: language_level=3, boundscheck=False, wraparound=False

import re
from typing import Optional, Dict, Any, List, Tuple, Callable


# Type converters for path parameters
PATH_CONVERTERS = {
    "int": int,
    "float": float,
    "str": str,
    "path": lambda x: x,
}

# Compiled regex for parameter parsing
PARAM_PATTERN = re.compile(r"\{(\w+)(?::(\w+))?\}")


cdef class Router:
    """Fast path router implemented in Cython."""

    cdef:
        dict routes
        dict websocket_routes
        dict _static_routes
        dict _ws_static_routes
        list _route_order
        list _ws_route_order
        dict _pattern_cache

    def __init__(self):
        self.routes = {}
        self.websocket_routes = {}
        self._static_routes = {}
        self._ws_static_routes = {}
        self._route_order = []
        self._ws_route_order = []
        self._pattern_cache = {}

    cpdef add_route(self, str path, str method, object handler):
        """Add a route to the router."""
        cdef:
            str method_upper = method.upper()
            str path_key = path
            dict methods
            list pattern_info
            bint has_params = False
            tuple item

        if path_key not in self.routes:
            self.routes[path_key] = {}
            # Cache pattern info at add time
            pattern_info = self._compile_pattern(path_key)
            self._pattern_cache[path_key] = pattern_info
            # Check if pattern has parameters
            has_params = False
            for item in pattern_info[0]:
                if item is not None:
                    has_params = True
                    break
            # Separate static and dynamic routes
            if not has_params:
                self._static_routes[path_key] = True
            else:
                self._route_order.append(path_key)
        
        methods = self.routes[path_key]
        methods[method_upper] = handler

    cpdef add_websocket_route(self, str path, object handler):
        """Add a WebSocket route to the router."""
        cdef:
            list pattern_info
            bint has_params = False
            tuple item
        
        if path not in self.websocket_routes:
            pattern_info = self._compile_pattern(path)
            self._pattern_cache[path] = pattern_info
            # Check if pattern has parameters
            has_params = False
            for item in pattern_info[0]:
                if item is not None:
                    has_params = True
                    break
            if not has_params:
                self._ws_static_routes[path] = True
            else:
                self._ws_route_order.append(path)
        
        self.websocket_routes[path] = handler

    cpdef tuple find_handler(self, str path, str method):
        """Find handler and path params for given path and method.

        Returns: (handler, path_params) or (None, None) if not found.
        """
        cdef:
            str method_upper = method.upper()
            dict methods
            object handler
            dict path_params
            str route_path
            list pattern_info

        # Exact match first (fast check for static routes)
        if path in self._static_routes:
            methods = self.routes[path]
            if method_upper in methods:
                return (methods[method_upper], {})

        # Pattern match (only for dynamic routes)
        for route_path in self._route_order:
            methods = self.routes[route_path]
            if method_upper not in methods:
                continue
            pattern_info = self._pattern_cache[route_path]
            path_params = self._match_path_fast(pattern_info, path)
            if path_params is not None:
                return (methods[method_upper], path_params)

        return (None, None)

    cpdef tuple find_websocket_handler(self, str path):
        """Find WebSocket handler for given path.

        Returns: (handler, path_params) or (None, None) if not found.
        """
        cdef:
            object handler
            dict path_params
            str route_path
            list pattern_info

        # Exact match first
        if path in self._ws_static_routes:
            return (self.websocket_routes[path], {})

        # Pattern match
        for route_path in self._ws_route_order:
            pattern_info = self._pattern_cache[route_path]
            path_params = self._match_path_fast(pattern_info, path)
            if path_params is not None:
                return (self.websocket_routes[route_path], path_params)

        return (None, None)

    cdef list _compile_pattern(self, str pattern):
        """Compile pattern into optimized structure.

        Returns: [(param_name, converter) or None for static parts]
        """
        cdef:
            list pattern_parts = pattern.strip("/").split("/")
            list compiled = []
            str part
            object match
            str param_name, param_type
            object converter

        for part in pattern_parts:
            match = PARAM_PATTERN.match(part)
            if match:
                param_name = match.group(1)
                param_type = match.group(2) or "str"
                
                if param_type not in PATH_CONVERTERS:
                    raise ValueError(f"Unknown path type: {param_type}")
                
                converter = PATH_CONVERTERS[param_type]
                compiled.append((param_name, converter))
            else:
                compiled.append(None)  # Static part

        return [compiled, pattern_parts]

    cdef dict _match_path_fast(self, list pattern_info, str path):
        """Fast path matching with precompiled pattern."""
        cdef:
            list compiled_pattern = pattern_info[0]
            list pattern_parts = pattern_info[1]
            list path_parts = path.strip("/").split("/")
            int i, n
            str path_part
            tuple param_info
            str param_name
            object converter
            dict path_params

        n = len(compiled_pattern)
        if len(path_parts) != n:
            return None

        path_params = {}

        for i in range(n):
            path_part = path_parts[i]
            param_info = compiled_pattern[i]

            if param_info is not None:
                # Dynamic parameter
                param_name = param_info[0]
                converter = param_info[1]
                try:
                    path_params[param_name] = converter(path_part)
                except (ValueError, TypeError):
                    return None
            elif pattern_parts[i] != path_part:
                # Static part mismatch
                return None

        return path_params if path_params else None

    cpdef list get_routes(self):
        """Get all registered routes."""
        return list(self.routes.keys())

    cpdef list get_websocket_routes(self):
        """Get all registered WebSocket routes."""
        return list(self.websocket_routes.keys())
