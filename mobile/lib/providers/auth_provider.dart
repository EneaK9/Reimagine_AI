import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Authentication state management
class AuthProvider with ChangeNotifier {
  // TODO: Use ApiService when backend auth is implemented
  // final ApiService _apiService = ApiService();
  
  User? _user;
  String? _token;
  bool _isLoading = false;
  String? _error;
  bool _isInitialized = false;

  // Getters
  User? get user => _user;
  String? get token => _token;
  bool get isLoading => _isLoading;
  String? get error => _error;
  bool get isLoggedIn => _token != null && _user != null;
  bool get isInitialized => _isInitialized;

  /// Initialize auth state from stored token
  Future<void> initialize() async {
    if (_isInitialized) return;
    
    try {
      final prefs = await SharedPreferences.getInstance();
      _token = prefs.getString('auth_token');
      
      if (_token != null) {
        // Validate token and get user info
        // For now, we'll just check if token exists
        // TODO: Add token validation endpoint
        final userData = prefs.getString('user_data');
        if (userData != null) {
          // Parse stored user data
          // _user = User.fromJson(jsonDecode(userData));
        }
      }
    } catch (e) {
      _error = e.toString();
    }
    
    _isInitialized = true;
    notifyListeners();
  }

  /// Login with email and password
  Future<bool> login(String email, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      // TODO: Call actual login API
      // For now, simulate login
      await Future.delayed(const Duration(seconds: 1));
      
      // Mock successful login
      _user = User(
        id: 'user_123',
        email: email,
        username: email.split('@').first,
      );
      _token = 'mock_token_${DateTime.now().millisecondsSinceEpoch}';
      
      // Store token
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', _token!);
      
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
      // TODO: Call actual register API
      // For now, simulate registration
      await Future.delayed(const Duration(seconds: 1));
      
      // Mock successful registration
      _user = User(
        id: 'user_${DateTime.now().millisecondsSinceEpoch}',
        email: email,
        username: username,
      );
      _token = 'mock_token_${DateTime.now().millisecondsSinceEpoch}';
      
      // Store token
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', _token!);
      
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
