class ShoppingListItem {
  final String itemName;
  final String searchDescription;
  final double budgetAllocation;
  final String placement;
  final String priority;

  const ShoppingListItem({
    required this.itemName,
    required this.searchDescription,
    required this.budgetAllocation,
    required this.placement,
    required this.priority,
  });

  factory ShoppingListItem.fromJson(Map<String, dynamic> json) {
    return ShoppingListItem(
      itemName: json['item_name'] ?? '',
      searchDescription: json['search_description'] ?? '',
      budgetAllocation: (json['budget_allocation'] ?? 0).toDouble(),
      placement: json['placement'] ?? '',
      priority: json['priority'] ?? 'must-have',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'item_name': itemName,
      'search_description': searchDescription,
      'budget_allocation': budgetAllocation,
      'placement': placement,
      'priority': priority,
    };
  }
}

class Product {
  final String title;
  final double price;
  final String currency;
  final String imageUrl;
  final String buyLink;
  final String store;
  final double? rating;
  final int? reviewCount;
  final String? description;

  const Product({
    required this.title,
    required this.price,
    required this.currency,
    required this.imageUrl,
    required this.buyLink,
    required this.store,
    this.rating,
    this.reviewCount,
    this.description,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      title: json['title'] ?? '',
      price: (json['price'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'USD',
      imageUrl: json['image_url'] ?? '',
      buyLink: json['buy_link'] ?? '',
      store: json['store'] ?? '',
      rating: json['rating'] == null
          ? null
          : (json['rating'] as num).toDouble(),
      reviewCount: json['review_count'],
      description: json['description'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'price': price,
      'currency': currency,
      'image_url': imageUrl,
      'buy_link': buyLink,
      'store': store,
      'rating': rating,
      'review_count': reviewCount,
      'description': description,
    };
  }
}

class ProductSearchResult {
  final ShoppingListItem shoppingListItem;
  final List<Product> allCandidates;

  const ProductSearchResult({
    required this.shoppingListItem,
    required this.allCandidates,
  });

  factory ProductSearchResult.fromJson(Map<String, dynamic> json) {
    return ProductSearchResult(
      shoppingListItem: ShoppingListItem.fromJson(
        json['shopping_list_item'] ?? {},
      ),
      allCandidates: (json['all_candidates'] as List? ?? [])
          .map((item) => Product.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
    );
  }
}

class SelectedProduct {
  final ShoppingListItem shoppingListItem;
  final Product chosenProduct;
  final List<Product> allCandidates;
  final String? reasoning;

  const SelectedProduct({
    required this.shoppingListItem,
    required this.chosenProduct,
    required this.allCandidates,
    this.reasoning,
  });

  factory SelectedProduct.fromJson(Map<String, dynamic> json) {
    return SelectedProduct(
      shoppingListItem: ShoppingListItem.fromJson(
        json['shopping_list_item'] ?? {},
      ),
      chosenProduct: Product.fromJson(json['chosen_product'] ?? {}),
      allCandidates: (json['all_candidates'] as List? ?? [])
          .map((item) => Product.fromJson(Map<String, dynamic>.from(item)))
          .toList(),
      reasoning: json['reasoning'],
    );
  }

  SelectedProduct copyWith({Product? chosenProduct}) {
    return SelectedProduct(
      shoppingListItem: shoppingListItem,
      chosenProduct: chosenProduct ?? this.chosenProduct,
      allCandidates: allCandidates,
      reasoning: reasoning,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'shopping_list_item': shoppingListItem.toJson(),
      'chosen_product': chosenProduct.toJson(),
      'all_candidates': allCandidates.map((item) => item.toJson()).toList(),
      'reasoning': reasoning,
    };
  }
}

class SceneAnalysis {
  final String spaceType;
  final List<String> existingItems;
  final String styleObservation;
  final List<ShoppingListItem> shoppingList;

  const SceneAnalysis({
    required this.spaceType,
    required this.existingItems,
    required this.styleObservation,
    required this.shoppingList,
  });

  factory SceneAnalysis.fromJson(Map<String, dynamic> json) {
    return SceneAnalysis(
      spaceType: json['space_type'] ?? '',
      existingItems: List<String>.from(json['existing_items'] ?? []),
      styleObservation: json['style_observation'] ?? '',
      shoppingList: (json['shopping_list'] as List? ?? [])
          .map(
            (item) =>
                ShoppingListItem.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'space_type': spaceType,
      'existing_items': existingItems,
      'style_observation': styleObservation,
      'shopping_list': shoppingList.map((item) => item.toJson()).toList(),
    };
  }
}

class RoomUpgradeAnalyzeResponse {
  final SceneAnalysis sceneAnalysis;
  final List<ProductSearchResult> searchResults;
  final List<SelectedProduct> selectedProducts;
  final double totalEstimated;
  final bool withinBudget;
  final double budget;
  final String currency;
  // Optional design advice (only present if yard inputs were provided)
  final YardDesignAdvice? designAdvice;

  const RoomUpgradeAnalyzeResponse({
    required this.sceneAnalysis,
    required this.searchResults,
    required this.selectedProducts,
    required this.totalEstimated,
    required this.withinBudget,
    required this.budget,
    required this.currency,
    this.designAdvice,
  });

  factory RoomUpgradeAnalyzeResponse.fromJson(Map<String, dynamic> json) {
    return RoomUpgradeAnalyzeResponse(
      sceneAnalysis: SceneAnalysis.fromJson(json['scene_analysis'] ?? {}),
      searchResults: (json['search_results'] as List? ?? [])
          .map(
            (item) =>
                ProductSearchResult.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(),
      selectedProducts: (json['selected_products'] as List? ?? [])
          .map(
            (item) => SelectedProduct.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(),
      totalEstimated: (json['total_estimated'] ?? 0).toDouble(),
      withinBudget: json['within_budget'] ?? true,
      budget: (json['budget'] ?? 0).toDouble(),
      currency: json['currency'] ?? 'USD',
      designAdvice: json['design_advice'] != null
          ? YardDesignAdvice.fromJson(json['design_advice'])
          : null,
    );
  }

  /// Check if design advice is available
  bool get hasDesignAdvice => designAdvice != null && !designAdvice!.isEmpty;
}

class RoomUpgradeGenerateResponse {
  final String? afterImageUrl;
  final List<String> generatedImages;
  final String promptUsed;

  const RoomUpgradeGenerateResponse({
    required this.afterImageUrl,
    required this.generatedImages,
    required this.promptUsed,
  });

  factory RoomUpgradeGenerateResponse.fromJson(Map<String, dynamic> json) {
    return RoomUpgradeGenerateResponse(
      afterImageUrl: json['after_image_url'],
      generatedImages: List<String>.from(json['generated_images'] ?? []),
      promptUsed: json['prompt_used'] ?? '',
    );
  }
}

// ============ Yard Designer Models ============

/// Optional inputs for yard design advisor.
/// All fields are optional - the system works without them.
class YardDesignInputs {
  final double? dimensionsSqm;
  final String? orientation;
  final String? surfaceType;
  final String? slope;
  final String? cityOrRegion;
  final String? environmentType;
  final String? primaryPurpose;
  final List<String>? whoUses;
  final String? maintenance;
  final String? stylePreference;
  final String? ownership;

  const YardDesignInputs({
    this.dimensionsSqm,
    this.orientation,
    this.surfaceType,
    this.slope,
    this.cityOrRegion,
    this.environmentType,
    this.primaryPurpose,
    this.whoUses,
    this.maintenance,
    this.stylePreference,
    this.ownership,
  });

  /// Check if any inputs were provided
  bool get hasInputs =>
      dimensionsSqm != null ||
      orientation != null ||
      surfaceType != null ||
      slope != null ||
      cityOrRegion != null ||
      environmentType != null ||
      primaryPurpose != null ||
      (whoUses != null && whoUses!.isNotEmpty) ||
      maintenance != null ||
      stylePreference != null ||
      ownership != null;

  /// Convert to form data format for multipart request
  Map<String, dynamic> toFormData() {
    return {
      if (dimensionsSqm != null) 'dimensions_sqm': dimensionsSqm,
      if (orientation != null) 'orientation': orientation,
      if (surfaceType != null) 'surface_type': surfaceType,
      if (slope != null) 'slope': slope,
      if (cityOrRegion != null) 'city_or_region': cityOrRegion,
      if (environmentType != null) 'environment_type': environmentType,
      if (primaryPurpose != null) 'primary_purpose': primaryPurpose,
      if (whoUses != null && whoUses!.isNotEmpty) 'who_uses': whoUses!.join(','),
      if (maintenance != null) 'maintenance': maintenance,
      if (stylePreference != null) 'style_preference': stylePreference,
      if (ownership != null) 'ownership': ownership,
    };
  }
}

/// A design constraint that applies to the user's situation.
class DesignConstraint {
  final String title;
  final String explanation;
  final String impact;
  final String userAction;

  const DesignConstraint({
    required this.title,
    required this.explanation,
    required this.impact,
    required this.userAction,
  });

  factory DesignConstraint.fromJson(Map<String, dynamic> json) {
    return DesignConstraint(
      title: json['title'] ?? '',
      explanation: json['explanation'] ?? '',
      impact: json['impact'] ?? '',
      userAction: json['user_action'] ?? '',
    );
  }
}

/// A step in the action plan for the user.
class ActionStep {
  final int step;
  final String action;
  final String detail;
  final String reasoning;

  const ActionStep({
    required this.step,
    required this.action,
    required this.detail,
    required this.reasoning,
  });

  factory ActionStep.fromJson(Map<String, dynamic> json) {
    return ActionStep(
      step: json['step'] ?? 0,
      action: json['action'] ?? '',
      detail: json['detail'] ?? '',
      reasoning: json['reasoning'] ?? '',
    );
  }
}

/// Requirements for a product category based on constraints.
class ProductRequirement {
  final String category;
  final String requirements;
  final List<String> searchTerms;
  final double budgetAllocation;
  final String placement;

  const ProductRequirement({
    required this.category,
    required this.requirements,
    required this.searchTerms,
    required this.budgetAllocation,
    required this.placement,
  });

  factory ProductRequirement.fromJson(Map<String, dynamic> json) {
    return ProductRequirement(
      category: json['category'] ?? '',
      requirements: json['requirements'] ?? '',
      searchTerms: List<String>.from(json['search_terms'] ?? []),
      budgetAllocation: (json['budget_allocation'] ?? 0).toDouble(),
      placement: json['placement'] ?? '',
    );
  }
}

/// A warning about the design or constraints.
class DesignWarning {
  final String severity;
  final String title;
  final String message;

  const DesignWarning({
    required this.severity,
    required this.title,
    required this.message,
  });

  factory DesignWarning.fromJson(Map<String, dynamic> json) {
    return DesignWarning(
      severity: json['severity'] ?? 'info',
      title: json['title'] ?? '',
      message: json['message'] ?? '',
    );
  }

  bool get isCritical => severity == 'critical';
  bool get isImportant => severity == 'important';
}

/// Seasonal care and expectations.
class SeasonalNotes {
  final String? spring;
  final String? summer;
  final String? autumn;
  final String? winter;

  const SeasonalNotes({
    this.spring,
    this.summer,
    this.autumn,
    this.winter,
  });

  factory SeasonalNotes.fromJson(Map<String, dynamic> json) {
    return SeasonalNotes(
      spring: json['spring'],
      summer: json['summer'],
      autumn: json['autumn'],
      winter: json['winter'],
    );
  }
}

/// Assessment of the user's space.
class SpaceAssessment {
  final String summary;
  final String? sizeCategory;
  final List<String> keyCharacteristics;

  const SpaceAssessment({
    required this.summary,
    this.sizeCategory,
    required this.keyCharacteristics,
  });

  factory SpaceAssessment.fromJson(Map<String, dynamic> json) {
    return SpaceAssessment(
      summary: json['summary'] ?? '',
      sizeCategory: json['size_category'],
      keyCharacteristics: List<String>.from(json['key_characteristics'] ?? []),
    );
  }
}

/// The overall design approach.
class DesignApproach {
  final String strategy;
  final String reasoning;
  final String? focalPoint;
  final List<String> zones;

  const DesignApproach({
    required this.strategy,
    required this.reasoning,
    this.focalPoint,
    required this.zones,
  });

  factory DesignApproach.fromJson(Map<String, dynamic> json) {
    return DesignApproach(
      strategy: json['strategy'] ?? '',
      reasoning: json['reasoning'] ?? '',
      focalPoint: json['focal_point'],
      zones: List<String>.from(json['zones'] ?? []),
    );
  }
}

/// Comprehensive design advice generated by the yard advisor.
class YardDesignAdvice {
  final SpaceAssessment? spaceAssessment;
  final List<DesignConstraint> keyConstraints;
  final DesignApproach? designApproach;
  final List<ActionStep> actionPlan;
  final List<ProductRequirement> productRequirements;
  final List<DesignWarning> warnings;
  final SeasonalNotes? seasonalNotes;

  const YardDesignAdvice({
    this.spaceAssessment,
    required this.keyConstraints,
    this.designApproach,
    required this.actionPlan,
    required this.productRequirements,
    required this.warnings,
    this.seasonalNotes,
  });

  factory YardDesignAdvice.fromJson(Map<String, dynamic> json) {
    return YardDesignAdvice(
      spaceAssessment: json['space_assessment'] != null
          ? SpaceAssessment.fromJson(json['space_assessment'])
          : null,
      keyConstraints: (json['key_constraints'] as List? ?? [])
          .map((e) => DesignConstraint.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      designApproach: json['design_approach'] != null
          ? DesignApproach.fromJson(json['design_approach'])
          : null,
      actionPlan: (json['action_plan'] as List? ?? [])
          .map((e) => ActionStep.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      productRequirements: (json['product_requirements'] as List? ?? [])
          .map((e) => ProductRequirement.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      warnings: (json['warnings'] as List? ?? [])
          .map((e) => DesignWarning.fromJson(Map<String, dynamic>.from(e)))
          .toList(),
      seasonalNotes: json['seasonal_notes'] != null
          ? SeasonalNotes.fromJson(json['seasonal_notes'])
          : null,
    );
  }

  /// Check if there are any critical warnings
  bool get hasCriticalWarnings => warnings.any((w) => w.isCritical);

  /// Check if advice is empty/not generated
  bool get isEmpty =>
      keyConstraints.isEmpty &&
      actionPlan.isEmpty &&
      productRequirements.isEmpty;
}
