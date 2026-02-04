import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/message.dart';
import '../models/conversation.dart';
import '../services/api_service.dart';

/// Chat state management
class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  Conversation? _currentConversation;
  List<ConversationSummary> _conversations = [];
  bool _isLoading = false;
  String? _error;
  File? _selectedImage;
  String? _currentMeshUrl;  // URL to 3D mesh for this conversation
  String? _currentMeshId;   // Mesh ID for editing the mesh

  // Getters
  Conversation? get currentConversation => _currentConversation;
  List<Message> get messages => _currentConversation?.messages ?? [];
  List<ConversationSummary> get conversations => _conversations;
  bool get isLoading => _isLoading;
  String? get error => _error;
  File? get selectedImage => _selectedImage;
  bool get hasSelectedImage => _selectedImage != null;
  String? get currentMeshUrl => _currentMeshUrl;
  String? get currentMeshId => _currentMeshId;
  bool get hasMesh => _currentMeshUrl != null && _currentMeshId != null;

  /// Start a new conversation
  void startNewConversation() {
    _currentConversation = Conversation.create();
    _currentMeshUrl = null;  // Clear mesh when starting new conversation
    _currentMeshId = null;   // Clear mesh ID too
    _error = null;
    notifyListeners();
  }

  /// Set selected image for upload
  void setSelectedImage(File? image) {
    _selectedImage = image;
    notifyListeners();
  }

  /// Clear selected image
  void clearSelectedImage() {
    _selectedImage = null;
    notifyListeners();
  }

  /// Set current mesh URL and ID (from Quick Scan or API response)
  void setCurrentMesh(String? meshId, String? meshUrl) {
    _currentMeshId = meshId;
    _currentMeshUrl = meshUrl;
    notifyListeners();
  }

  /// Set current mesh URL (from Quick Scan or API response) - legacy support
  void setCurrentMeshUrl(String? meshUrl) {
    _currentMeshUrl = meshUrl;
    notifyListeners();
  }

  /// Clear current mesh
  void clearCurrentMesh() {
    _currentMeshUrl = null;
    _currentMeshId = null;
    notifyListeners();
  }

  /// Get full mesh URL for ModelViewer
  String? getFullMeshUrl() {
    if (_currentMeshUrl == null) return null;
    return _apiService.getFullMeshUrl(_currentMeshUrl!);
  }

  /// Send a message
  Future<void> sendMessage(String content) async {
    if (content.trim().isEmpty && _selectedImage == null) return;

    _error = null;
    
    // Create conversation if needed
    _currentConversation ??= Conversation.create();

    // Add user message
    final userMessage = Message.user(
      content,
      imageUrl: _selectedImage?.path,
    );
    _currentConversation = _currentConversation!.addMessage(userMessage);
    
    // Add loading indicator
    _currentConversation = _currentConversation!.addMessage(Message.loading());
    notifyListeners();

    try {
      ChatResponse response;
      
      if (_selectedImage != null) {
        // Send with image - include mesh_id if we have one
        response = await _apiService.sendMessageWithImage(
          message: content,
          imageFile: _selectedImage!,
          conversationId: _currentConversation!.id,
          meshId: _currentMeshId,  // Pass mesh_id for editing
        );
        _selectedImage = null; // Clear after sending
      } else {
        // Send text only - include mesh_id if we have one
        response = await _apiService.sendMessage(
          message: content,
          conversationId: _currentConversation!.id,
          meshId: _currentMeshId,  // Pass mesh_id for editing
        );
      }

      // Remove loading message
      final messagesWithoutLoading = _currentConversation!.messages
          .where((m) => !m.isLoading)
          .toList();

      // Add assistant response
      final assistantMessage = Message.assistant(
        response.message,
        imageUrls: response.generatedImages,
      );

      _currentConversation = _currentConversation!.copyWith(
        id: response.conversationId,
        messages: [...messagesWithoutLoading, assistantMessage],
      );

      // Update mesh info if returned from API (mesh was regenerated/updated)
      if (response.meshUrl != null) {
        _currentMeshUrl = response.meshUrl;
      }
      if (response.meshId != null) {
        _currentMeshId = response.meshId;
      }

    } catch (e) {
      // Remove loading message on error
      final messagesWithoutLoading = _currentConversation!.messages
          .where((m) => !m.isLoading)
          .toList();
      
      _currentConversation = _currentConversation!.copyWith(
        messages: messagesWithoutLoading,
      );
      
      _error = e.toString();
    }

    notifyListeners();
  }

  /// Load conversation history
  Future<void> loadConversations() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _conversations = await _apiService.getConversations();
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Load a specific conversation
  Future<void> loadConversation(String conversationId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _apiService.getConversation(conversationId);
      _currentConversation = Conversation.fromJson(data);
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Delete a conversation
  Future<void> deleteConversation(String conversationId) async {
    try {
      await _apiService.deleteConversation(conversationId);
      
      // Remove from local list
      _conversations.removeWhere((c) => c.id == conversationId);
      
      // If deleted conversation was current, clear it
      if (_currentConversation?.id == conversationId) {
        _currentConversation = null;
      }
      
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  /// Check backend health
  Future<bool> checkHealth() async {
    return await _apiService.healthCheck();
  }

  /// Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
