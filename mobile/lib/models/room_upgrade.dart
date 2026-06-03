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

  const RoomUpgradeAnalyzeResponse({
    required this.sceneAnalysis,
    required this.searchResults,
    required this.selectedProducts,
    required this.totalEstimated,
    required this.withinBudget,
    required this.budget,
    required this.currency,
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
    );
  }
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
