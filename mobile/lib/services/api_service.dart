import 'dart:io';
import 'package:dio/dio.dart';
import '../config/api_config.dart';

/// API Service for communicating with the backend (Singleton)
class ApiService {
  // Singleton instance
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  
  late final Dio _dio;
  String? _authToken;

  ApiService._internal() {
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
    String? meshId,  // Pass mesh_id so backend can edit the mesh
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.chat,
        data: {
          'message': message,
          'conversation_id': conversationId,
          'image_base64': imageBase64,
          if (meshId != null) 'mesh_id': meshId,
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
    String? meshId,  // Pass mesh_id so backend can edit the mesh
  }) async {
    try {
      final formData = FormData.fromMap({
        'message': message,
        'conversation_id': conversationId,
        if (meshId != null) 'mesh_id': meshId,
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

  // ============ Depth/3D Mesh Methods ============

  /// Generate a 3D mesh from a room photo using depth estimation
  Future<Map<String, dynamic>> generateMeshFromPhoto(File imageFile) async {
    try {
      final formData = FormData.fromMap({
        'image': await MultipartFile.fromFile(
          imageFile.path,
          filename: imageFile.path.split('/').last,
        ),
      });

      final response = await _dio.post(
        ApiConfig.depthGenerateMeshUpload,
        data: formData,
        options: Options(
          headers: {'Content-Type': 'multipart/form-data'},
          sendTimeout: ApiConfig.longReceiveTimeout,
          receiveTimeout: ApiConfig.longReceiveTimeout, // 10 min for CPU processing
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Generate a 3D mesh from a base64 encoded image
  Future<Map<String, dynamic>> generateMeshFromBase64({
    required String imageBase64,
    String? conversationId,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.depthGenerateMesh,
        data: {
          'image_base64': imageBase64,
          'conversation_id': conversationId,
        },
        options: Options(
          receiveTimeout: ApiConfig.longReceiveTimeout, // 10 min for CPU processing
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Get mesh info by ID
  Future<Map<String, dynamic>> getMeshInfo(String meshId) async {
    try {
      final response = await _dio.get(ApiConfig.depthMeshInfo(meshId));
      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// List all generated meshes
  Future<List<Map<String, dynamic>>> listMeshes() async {
    try {
      final response = await _dio.get(ApiConfig.depthMeshes);
      return List<Map<String, dynamic>>.from(response.data['meshes'] ?? []);
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Delete a mesh by ID
  Future<void> deleteMesh(String meshId) async {
    try {
      await _dio.delete(ApiConfig.depthMesh(meshId));
    } on DioException catch (e) {
      throw _handleError(e);
    }
  }

  /// Get full URL for a mesh (for loading in ModelViewer)
  String getFullMeshUrl(String meshPath) {
    // meshPath is like /api/v1/depth/mesh/mesh_abc123
    return '${ApiConfig.baseUrl}$meshPath';
  }

  /// Regenerate mesh from edited image
  Future<Map<String, dynamic>> updateMesh({
    required String imageBase64,
    String? conversationId,
  }) async {
    try {
      final response = await _dio.post(
        ApiConfig.depthUpdateMesh,
        data: {
          'image_base64': imageBase64,
          'conversation_id': conversationId,
        },
        options: Options(
          receiveTimeout: ApiConfig.longReceiveTimeout, // 10 min for CPU processing
        ),
      );

      return response.data;
    } on DioException catch (e) {
      throw _handleError(e);
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
  final String? meshUrl;  // URL to updated 3D mesh (if conversation has mesh)
  final String? meshId;   // Mesh ID for further edits

  ChatResponse({
    required this.conversationId,
    required this.message,
    this.generatedImages = const [],
    this.furnitureSuggestions = const [],
    this.meshUrl,
    this.meshId,
  });

  factory ChatResponse.fromJson(Map<String, dynamic> json) {
    return ChatResponse(
      conversationId: json['conversation_id'] ?? '',
      message: json['message'] ?? '',
      generatedImages: List<String>.from(json['generated_images'] ?? []),
      furnitureSuggestions: List<Map<String, dynamic>>.from(
        json['furniture_suggestions'] ?? [],
      ),
      meshUrl: json['mesh_url'],
      meshId: json['mesh_id'],
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
