import 'dart:convert';

/// Represents a scanned 3D room
class RoomModel {
  final String id;
  final String name;
  final String filePath;
  final DateTime createdAt;
  final DateTime? updatedAt;
  final RoomMetadata? metadata;
  
  RoomModel({
    required this.id,
    required this.name,
    required this.filePath,
    required this.createdAt,
    this.updatedAt,
    this.metadata,
  });
  
  factory RoomModel.fromJson(Map<String, dynamic> json) {
    return RoomModel(
      id: json['id'] ?? '',
      name: json['name'] ?? 'Untitled Room',
      filePath: json['file_path'] ?? json['filePath'] ?? '',
      createdAt: json['created_at'] != null 
          ? DateTime.parse(json['created_at']) 
          : DateTime.now(),
      updatedAt: json['updated_at'] != null 
          ? DateTime.parse(json['updated_at']) 
          : null,
      metadata: json['metadata'] != null 
          ? RoomMetadata.fromJson(json['metadata']) 
          : null,
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'file_path': filePath,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'metadata': metadata?.toJson(),
    };
  }
  
  RoomModel copyWith({
    String? id,
    String? name,
    String? filePath,
    DateTime? createdAt,
    DateTime? updatedAt,
    RoomMetadata? metadata,
  }) {
    return RoomModel(
      id: id ?? this.id,
      name: name ?? this.name,
      filePath: filePath ?? this.filePath,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      metadata: metadata ?? this.metadata,
    );
  }
}

/// Metadata about the scanned room
class RoomMetadata {
  final int? vertexCount;
  final int? triangleCount;
  final double? fileSizeBytes;
  final RoomDimensions? dimensions;
  final List<RoomPart>? detectedParts;
  final String? scanQuality; // 'low', 'medium', 'high'
  final String? deviceType; // Device used for scanning
  
  RoomMetadata({
    this.vertexCount,
    this.triangleCount,
    this.fileSizeBytes,
    this.dimensions,
    this.detectedParts,
    this.scanQuality,
    this.deviceType,
  });
  
  factory RoomMetadata.fromJson(Map<String, dynamic> json) {
    return RoomMetadata(
      vertexCount: json['vertex_count'],
      triangleCount: json['triangle_count'],
      fileSizeBytes: json['file_size_bytes']?.toDouble(),
      dimensions: json['dimensions'] != null 
          ? RoomDimensions.fromJson(json['dimensions']) 
          : null,
      detectedParts: json['detected_parts'] != null
          ? (json['detected_parts'] as List)
              .map((p) => RoomPart.fromJson(p))
              .toList()
          : null,
      scanQuality: json['scan_quality'],
      deviceType: json['device_type'],
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'vertex_count': vertexCount,
      'triangle_count': triangleCount,
      'file_size_bytes': fileSizeBytes,
      'dimensions': dimensions?.toJson(),
      'detected_parts': detectedParts?.map((p) => p.toJson()).toList(),
      'scan_quality': scanQuality,
      'device_type': deviceType,
    };
  }
}

/// Room dimensions in meters
class RoomDimensions {
  final double width;
  final double height;
  final double depth;
  
  RoomDimensions({
    required this.width,
    required this.height,
    required this.depth,
  });
  
  factory RoomDimensions.fromJson(Map<String, dynamic> json) {
    return RoomDimensions(
      width: (json['width'] ?? 0).toDouble(),
      height: (json['height'] ?? 0).toDouble(),
      depth: (json['depth'] ?? 0).toDouble(),
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'width': width,
      'height': height,
      'depth': depth,
    };
  }
  
  double get volume => width * height * depth;
  double get floorArea => width * depth;
}

/// Represents a detected part of the room
class RoomPart {
  final String name;
  final RoomPartType type;
  final String? materialId;
  final MaterialProperties? currentMaterial;
  
  RoomPart({
    required this.name,
    required this.type,
    this.materialId,
    this.currentMaterial,
  });
  
  factory RoomPart.fromJson(Map<String, dynamic> json) {
    return RoomPart(
      name: json['name'] ?? '',
      type: RoomPartType.fromString(json['type'] ?? 'other'),
      materialId: json['material_id'],
      currentMaterial: json['current_material'] != null
          ? MaterialProperties.fromJson(json['current_material'])
          : null,
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'type': type.name,
      'material_id': materialId,
      'current_material': currentMaterial?.toJson(),
    };
  }
}

/// Types of room parts
enum RoomPartType {
  wall,
  floor,
  ceiling,
  door,
  window,
  furniture,
  other;
  
  static RoomPartType fromString(String value) {
    return RoomPartType.values.firstWhere(
      (e) => e.name == value.toLowerCase(),
      orElse: () => RoomPartType.other,
    );
  }
}

/// Material properties for a room part
class MaterialProperties {
  final String? color; // Hex color
  final String? textureUrl;
  final String? materialPreset;
  final double? metallic;
  final double? roughness;
  
  MaterialProperties({
    this.color,
    this.textureUrl,
    this.materialPreset,
    this.metallic,
    this.roughness,
  });
  
  factory MaterialProperties.fromJson(Map<String, dynamic> json) {
    return MaterialProperties(
      color: json['color'],
      textureUrl: json['texture_url'],
      materialPreset: json['material_preset'],
      metallic: json['metallic']?.toDouble(),
      roughness: json['roughness']?.toDouble(),
    );
  }
  
  Map<String, dynamic> toJson() {
    return {
      'color': color,
      'texture_url': textureUrl,
      'material_preset': materialPreset,
      'metallic': metallic,
      'roughness': roughness,
    };
  }
}

/// Represents a material edit request
class MaterialEditRequest {
  final String target; // wall, floor, ceiling, etc.
  final String property; // color, texture, material
  final String value; // hex color, URL, or preset name
  
  MaterialEditRequest({
    required this.target,
    required this.property,
    required this.value,
  });
  
  Map<String, dynamic> toJson() {
    return {
      'target': target,
      'property': property,
      'value': value,
    };
  }
  
  String toJsonString() => jsonEncode(toJson());
  
  factory MaterialEditRequest.color(String target, String hexColor) {
    return MaterialEditRequest(
      target: target,
      property: 'color',
      value: hexColor,
    );
  }
  
  factory MaterialEditRequest.texture(String target, String textureUrl) {
    return MaterialEditRequest(
      target: target,
      property: 'texture',
      value: textureUrl,
    );
  }
  
  factory MaterialEditRequest.material(String target, String presetName) {
    return MaterialEditRequest(
      target: target,
      property: 'material',
      value: presetName,
    );
  }
}

/// Response from AI edit parsing
class MaterialEditResponse {
  final MaterialEditRequest edit;
  final String aiResponse;
  
  MaterialEditResponse({
    required this.edit,
    required this.aiResponse,
  });
  
  factory MaterialEditResponse.fromJson(Map<String, dynamic> json) {
    return MaterialEditResponse(
      edit: MaterialEditRequest(
        target: json['edit']['target'] ?? '',
        property: json['edit']['property'] ?? '',
        value: json['edit']['value'] ?? '',
      ),
      aiResponse: json['ai_response'] ?? '',
    );
  }
}
