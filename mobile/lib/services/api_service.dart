import 'dart:io';
import 'package:dio/dio.dart';
import '../config/api_config.dart';

/// API Service for communicating with the backend
class ApiService {
  late final Dio _dio;
  String? _authToken;

  ApiService() {
    _dio = Dio(BaseOptions(
      baseUrl: ApiConfig.baseUrl,
      connectTimeout: ApiConfig.connectTimeout,
      receiveTimeout: ApiConfig.receiveTimeout,
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ));

    // Add logging interceptor for debugging
    _dio.interceptors.add(LogInterceptor(
      requestBody: true,
      responseBody: true,
      logPrint: (obj) => print('[API] $obj'),
    ));
  }

  /// Set auth token for authenticated requests
  void setAuthToken(String? token) {
    _authToken = token;
    if (token != null) {
      _dio.options.headers['Authorization'] = 'Bearer $token';
    } else {
      _dio.options.headers.remove('Authorization');
    }
  }

  // ============ Auth Methods ============

  /// Login user
  Future<AuthResponse> login(String email, String password) async {
    try {
      final response = await _dio.post(
        ApiConfig.login,
        data: {
          'email': email,
          'password': password,
        },
      );
      final authResponse = AuthResponse.fromJson(response.data);
      setAuthToken(authResponse.token);
      return authResponse;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Sign up new user
  Future<AuthResponse> signup(String username, String email, String password) async {
    try {
      final response = await _dio.post(
        ApiConfig.signup,
        data: {
          'username': username,
          'email': email,
          'password': password,
        },
      );
      final authResponse = AuthResponse.fromJson(response.data);
      setAuthToken(authResponse.token);
      return authResponse;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Logout user
  Future<void> logout() async {
    try {
      await _dio.post(ApiConfig.logout);
    } catch (e) {
      // Ignore logout errors
    }
    setAuthToken(null);
  }

  /// Send a chat message
  Future<ChatResponse> sendMessage({
    required String message,
    String? conversationId,
    String? imageBase64,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.chat,
        data: {
          'message': message,
          'conversation_id': conversationId,
          'image_base64': imageBase64,
        },
      );

      return ChatResponse.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Send a chat message with an image file
  Future<ChatResponse> sendMessageWithImage({
    required String message,
    required File imageFile,
    String? conversationId,
  }) async {
    try {
      final formData = FormData.fromMap({
        'message': message,
        'conversation_id': conversationId,
        'image': await MultipartFile.fromFile(
          imageFile.path,
          filename: imageFile.path.split('/').last,
        ),
      });

      final response = await _dio.post(
        ApiConfig.chatWithImage,
        data: formData,
        options: Options(
          headers: {'Content-Type': 'multipart/form-data'},
        ),
      );

      return ChatResponse.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Get all conversations
  Future<List<ConversationSummary>> getConversations() async {
    try {
      final response = await _dio.get(ApiConfig.conversations);
      return (response.data as List)
          .map((c) => ConversationSummary.fromJson(c))
          .toList();
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Get a specific conversation
  Future<Map<String, dynamic>> getConversation(String conversationId) async {
    try {
      final response = await _dio.get('${ApiConfig.conversations}/$conversationId');
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Delete a conversation
  Future<void> deleteConversation(String conversationId) async {
    try {
      await _dio.delete('${ApiConfig.conversations}/$conversationId');
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Generate room images from prompt
  Future<ImageGenerationResponse> generateImages({
    required String prompt,
    String style = 'modern',
    int numVariations = 4,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.generateImages,
        data: {
          'prompt': prompt,
          'style': style,
          'num_variations': numVariations,
        },
      );

      return ImageGenerationResponse.fromJson(response.data);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Analyze a room image
  Future<Map<String, dynamic>> analyzeRoom(File imageFile) async {
    try {
      final formData = FormData.fromMap({
        'image': await MultipartFile.fromFile(
          imageFile.path,
          filename: imageFile.path.split('/').last,
        ),
      });

      final response = await _dio.post(
        ApiConfig.analyzeRoom,
        data: formData,
        options: Options(
          headers: {'Content-Type': 'multipart/form-data'},
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Check if backend is healthy
  Future<bool> healthCheck() async {
    try {
      final response = await _dio.get('/health');
      return response.data['status'] == 'healthy';
    } catch (e) {
      return false;
    }
  }

  /// Handle API errors
  ApiException _handleError(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiException('Connection timed out. Please try again.');
      case DioExceptionType.connectionError:
        return ApiException(
          'Cannot connect to server. Make sure the backend is running.',
        );
      case DioExceptionType.badResponse:
        final message = e.response?.data?['detail'] ?? 
                        e.response?.data?['message'] ?? 
                        'Server error occurred';
        return ApiException(message);
      default:
        return ApiException('An unexpected error occurred: ${e.message}');
    }
  }
}

/// API Exception
class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

/// Chat Response from API
class ChatResponse {
  final String conversationId;
  final String message;
  final List<String> generatedImages;
  final List<Map<String, dynamic>> furnitureSuggestions;

  ChatResponse({
    required this.conversationId,
    required this.message,
    this.generatedImages = const [],
    this.furnitureSuggestions = const [],
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      conversationId: json['conversation_id'] ?? '',
      message: json['message'] ?? '',
      generatedImages: List<String>.from(json['generated_images'] ?? []),
      furnitureSuggestions: List<Map<String, dynamic>>.from(
        json['furniture_suggestions'] ?? [],
      ),
    );
  }
}

/// Conversation Summary
class ConversationSummary {
  final String id;
  final String title;
  final String? lastMessage;
  final int imageCount;
  final DateTime createdAt;
  final DateTime updatedAt;

  ConversationSummary({
    required this.id,
    required this.title,
    this.lastMessage,
    this.imageCount = 0,
    required this.createdAt,
    required this.updatedAt,
  });

  factory ConversationSummary.fromJson(Map<String, dynamic> json) {
    return ConversationSummary(
      id: json['id'] ?? '',
      title: json['title'] ?? 'Untitled',
      lastMessage: json['last_message'],
      imageCount: json['image_count'] ?? 0,
      createdAt: DateTime.parse(json['created_at']),
      updatedAt: DateTime.parse(json['updated_at']),
    );
  }
}

/// Image Generation Response
class ImageGenerationResponse {
  final List<GeneratedImage> images;

  ImageGenerationResponse({required this.images});

  factory ImageGenerationResponse.fromJson(Map<String, dynamic> json) {
    return ImageGenerationResponse(
      images: (json['images'] as List)
          .map((i) => GeneratedImage.fromJson(i))
          .toList(),
    );
  }
}

/// Generated Image
class GeneratedImage {
  final String url;
  final String promptUsed;
  final String style;

  GeneratedImage({
    required this.url,
    required this.promptUsed,
    required this.style,
  });

  factory GeneratedImage.fromJson(Map<String, dynamic> json) {
    return GeneratedImage(
      url: json['url'] ?? '',
      promptUsed: json['prompt_used'] ?? '',
      style: json['style'] ?? '',
    );
  }
}

/// Auth Response from API
class AuthResponse {
  final String id;
  final String username;
  final String email;
  final String token;
  final String? createdAt;

  AuthResponse({
    required this.id,
    required this.username,
    required this.email,
    required this.token,
    this.createdAt,
  });

  factory AuthResponse.fromJson(Map<String, dynamic> json) {
    return AuthResponse(
      id: json['id'] ?? '',
      username: json['username'] ?? '',
      email: json['email'] ?? '',
      token: json['token'] ?? '',
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'username': username,
      'email': email,
      'token': token,
      'created_at': createdAt,
    };
  }
}
