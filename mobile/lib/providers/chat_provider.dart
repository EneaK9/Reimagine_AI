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
  String? _currentSceneId;  // Editable 3D scene attached to this conversation
  bool _sceneJustUpdated = false; // Last message changed the 3D scene
  bool _conversationPersisted = false; // Current conversation exists on the backend
  int _conversationGeneration = 0; // Bumped when another conversation becomes current

  // Getters
  Conversation? get currentConversation => _currentConversation;

  /// ID of the current conversation if it exists on the backend (loaded from
  /// history, or a message has round-tripped). Null for a local draft.
  String? get persistedConversationId =>
      _conversationPersisted ? _currentConversation?.id : null;

  /// Changes whenever a different conversation becomes current (new, loaded
  /// or deleted). Unlike the id, it survives a draft getting its server id.
  int get conversationGeneration => _conversationGeneration;

  List<Message> get messages => _currentConversation?.messages ?? [];
  List<ConversationSummary> get conversations => _conversations;
  bool get isLoading => _isLoading;
  String? get error => _error;
  File? get selectedImage => _selectedImage;
  bool get hasSelectedImage => _selectedImage != null;
  String? get currentMeshUrl => _currentMeshUrl;
  String? get currentMeshId => _currentMeshId;
  bool get hasMesh => _currentMeshUrl != null && _currentMeshId != null;
  String? get currentSceneId => _currentSceneId;
  bool get hasScene => _currentSceneId != null;
  bool get sceneJustUpdated => _sceneJustUpdated;

  /// Attach an editable 3D scene to the current conversation
  void setCurrentScene(String? sceneId) {
    _currentSceneId = sceneId;
    notifyListeners();
  }

  /// Start a new conversation
  void startNewConversation() {
    _currentConversation = Conversation.create();
    _conversationPersisted = false;
    _conversationGeneration++;
    _currentMeshUrl = null;  // Clear mesh when starting new conversation
    _currentMeshId = null;   // Clear mesh ID too
    _currentSceneId = null;
    _sceneJustUpdated = false;
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
    final generation = _conversationGeneration;
    
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
        // Send with image - include mesh_id / scene_id if we have them
        response = await _apiService.sendMessageWithImage(
          message: content,
          imageFile: _selectedImage!,
          conversationId: _currentConversation!.id,
          meshId: _currentMeshId,  // Pass mesh_id for editing
          sceneId: _currentSceneId, // Link the 3D room to this conversation
        );
        _selectedImage = null; // Clear after sending
      } else {
        // Send text only - include mesh_id / scene_id if we have them
        response = await _apiService.sendMessage(
          message: content,
          conversationId: _currentConversation!.id,
          meshId: _currentMeshId,  // Pass mesh_id for editing
          sceneId: _currentSceneId, // Link the 3D room to this conversation
        );
      }

      // The user switched conversations while waiting: this reply belongs
      // to the other one (it is saved on the backend), so leave state alone.
      if (generation != _conversationGeneration) {
        notifyListeners();
        return;
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
      _conversationPersisted = true;

      // Update mesh info if returned from API (mesh was regenerated/updated)
      if (response.meshUrl != null) {
        _currentMeshUrl = response.meshUrl;
      }
      if (response.meshId != null) {
        _currentMeshId = response.meshId;
      }

      // Track the editable 3D scene (edited via chat on the backend)
      if (response.sceneId != null) {
        _currentSceneId = response.sceneId;
      }
      _sceneJustUpdated = response.sceneUpdated;

    } catch (e) {
      // Remove loading message on error
      final conversation = _currentConversation;
      if (generation == _conversationGeneration && conversation != null) {
        _currentConversation = conversation.copyWith(
          messages: conversation.messages.where((m) => !m.isLoading).toList(),
        );
      }
      
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
      final conversation = Conversation.fromJson(data);
      _currentConversation = conversation;
      _conversationPersisted = true;
      _conversationGeneration++;
      // Mesh/scene state belonged to the previous conversation; restore the
      // loaded conversation's own 3D room (if it has one).
      _currentMeshUrl = null;
      _currentMeshId = null;
      _currentSceneId = conversation.sceneId;
      _sceneJustUpdated = false;
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
      
      // If deleted conversation was current, clear it (and its 3D state)
      if (_currentConversation?.id == conversationId) {
        _currentConversation = null;
        _conversationPersisted = false;
        _conversationGeneration++;
        _currentMeshUrl = null;
        _currentMeshId = null;
        _currentSceneId = null;
        _sceneJustUpdated = false;
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
