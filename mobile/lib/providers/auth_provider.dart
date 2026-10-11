import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';

/// Authentication state management
class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  User? _user;
  String? _token;
  bool _isLoading = false;
  String? _error;
  bool _isInitialized = false;
  Future<void>? _initializing;
  bool _sessionExpired = false;
  bool _disposed = false;

  AuthProvider() {
    _apiService.onUnauthorized = _handleUnauthorized;
  }

  // Getters
  User? get user => _user;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _token != null && _user != null;
  bool get isInitialized => _isInitialized;

  /// Restore the saved session (called once at app startup).
  Future<void> initialize() => _initializing ??= _restoreSession();

  Future<void> _restoreSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final token = prefs.getString('auth_token');

      if (token != null && token.isNotEmpty) {
        _token = token;
        _apiService.setAuthToken(token);

        // Load stored user data
        final userData = prefs.getString('user_data');
        if (userData != null) {
          _user = User.fromJson(jsonDecode(userData) as Map<String, dynamic>);
        }

        await _validateSession();
      }
    } catch (e) {
      debugPrint('[Auth] Could not restore the saved session: $e');
    }

    _isInitialized = true;
    _notify();
  }

  /// Check the restored token with the backend. A 401 signs the user out;
  /// network trouble keeps the session so the app still opens when the
  /// server is slow or unreachable (a later 401 still signs out).
  Future<void> _validateSession() async {
    try {
      final me = await _apiService
          .getCurrentUser()
          .timeout(const Duration(seconds: 6));
      if (_token == null) return; // rejected meanwhile
      _user = User(
        id: me['id']?.toString() ?? _user?.id ?? '',
        email: me['email']?.toString() ?? _user?.email ?? '',
        username: me['username']?.toString() ?? _user?.username ?? '',
        avatarUrl: _user?.avatarUrl,
      );
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('user_data', jsonEncode(_user!.toJson()));
    } on ApiException catch (e) {
      if (e.statusCode == 401) {
        _forgetSession();
        await _clearStoredSession();
      }
    } catch (e) {
      debugPrint('[Auth] Session check skipped: $e');
    }
  }

  /// The backend rejected the current token (see [ApiService.onUnauthorized]).
  void _handleUnauthorized() {
    if (_token == null) return;
    // During startup the first screen simply becomes sign-in; afterwards the
    // app is told to send the user back there.
    if (_isInitialized) _sessionExpired = true;
    _forgetSession();
    _notify();
    unawaited(_clearStoredSession());
  }

  /// Returns true once after the session was rejected by the backend.
  bool consumeSessionExpired() {
    final expired = _sessionExpired;
    _sessionExpired = false;
    return expired;
  }

  void _forgetSession() {
    _user = null;
    _token = null;
    _apiService.setAuthToken(null);
  }

  Future<void> _clearStoredSession() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove('auth_token');
      await prefs.remove('user_data');
    } catch (e) {
      debugPrint('[Auth] Could not clear the saved session: $e');
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    if (_apiService.onUnauthorized == _handleUnauthorized) {
      _apiService.onUnauthorized = null;
    }
    super.dispose();
  }

  /// Login with email and password
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _apiService.login(email, password);

      _sessionExpired = false;
      _user = User(
        id: response.id,
        email: response.email,
        username: response.username,
      );
      _token = response.token;
      
      // Store credentials
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', _token!);
      await prefs.setString('user_data', jsonEncode(_user!.toJson()));
      
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Register new user
  Future<bool> register(String email, String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final response = await _apiService.signup(username, email, password);

      _sessionExpired = false;
      _user = User(
        id: response.id,
        email: response.email,
        username: response.username,
      );
      _token = response.token;
      
      // Store credentials
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', _token!);
      await prefs.setString('user_data', jsonEncode(_user!.toJson()));
      
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout
  Future<void> logout() async {
    try {
      await _apiService.logout();
    } catch (e) {
      // Ignore logout errors
    }
    
    _user = null;
    _token = null;
    
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('user_data');
    
    notifyListeners();
  }

  /// Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}

/// User model
class User {
  final String id;
  final String email;
  final String username;
  final String? avatarUrl;

  User({
    required this.id,
    required this.email,
    required this.username,
    this.avatarUrl,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] ?? '',
      email: json['email'] ?? '',
      username: json['username'] ?? '',
      avatarUrl: json['avatar_url'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'email': email,
      'username': username,
      'avatar_url': avatarUrl,
    };
  }
}
