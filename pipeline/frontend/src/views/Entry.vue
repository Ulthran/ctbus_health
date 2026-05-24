<template>
  <v-container class="py-6" style="max-width:600px">

    <!-- Today so far -->
    <v-card v-if="todayTotals" class="mb-4" rounded="lg" elevation="1">
      <v-card-text>
        <div class="d-flex align-center justify-space-between mb-2">
          <span class="text-subtitle-2">Today so far</span>
          <span class="text-caption text-grey">{{ todayEntryCount }} {{ todayEntryCount === 1 ? 'entry' : 'entries' }}</span>
        </div>
        <div class="d-flex align-baseline gap-2 mb-1">
          <span class="text-h5 font-weight-bold text-green-darken-2">{{ Math.round(todayTotals.kcal) }}</span>
          <span class="text-caption text-grey">/ 2,000 kcal</span>
          <v-chip size="x-small" :color="todayTotals.kcal > 2000 ? 'orange' : 'green-darken-2'" variant="tonal" class="ml-auto">
            {{ Math.round(todayTotals.kcal / 2000 * 100) }}% DV
          </v-chip>
        </div>
        <div style="height:8px;border-radius:4px;background:#eee;overflow:hidden;margin-bottom:8px">
          <div :style="{ width: Math.min(100, todayTotals.kcal / 2000 * 100) + '%', height: '100%', background: todayTotals.kcal > 2000 ? '#FF9800' : '#4CAF50' }" />
        </div>
        <div class="d-flex gap-4 text-caption">
          <span><span class="font-weight-medium">{{ Math.round(todayTotals.protein) }}g</span><span class="text-grey ml-1">protein ({{ Math.round(todayTotals.protein / 50 * 100) }}%)</span></span>
          <span><span class="font-weight-medium">{{ Math.round(todayTotals.fat) }}g</span><span class="text-grey ml-1">fat</span></span>
          <span><span class="font-weight-medium">{{ Math.round(todayTotals.carbs) }}g</span><span class="text-grey ml-1">carbs</span></span>
        </div>
      </v-card-text>
    </v-card>

    <!-- Date / time -->
    <v-card class="mb-4" rounded="lg" elevation="1">
      <v-card-text>
        <v-row dense align="center">
          <v-col cols="7">
            <v-text-field v-model="date" type="date" label="Date" density="compact" variant="outlined" hide-details />
          </v-col>
          <v-col cols="5">
            <v-text-field v-model="time" type="time" label="Time" density="compact" variant="outlined" hide-details />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Recipe / Restaurant loader -->
    <v-card class="mb-4" rounded="lg" elevation="1">
      <v-card-text class="pb-3">
        <!-- Mini tab switcher -->
        <div class="d-flex mb-2" style="border-bottom:1px solid #eeeeee;margin:-4px -4px 8px">
          <div
            @click="loaderTab = 'recipe'"
            style="padding:5px 12px 7px;font-size:11px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;user-select:none;color:#757575"
            :style="loaderTab === 'recipe' ? 'border-color:#2e7d32;color:#2e7d32' : ''"
          >
            <i class="fas fa-layer-group" style="font-size:10px;margin-right:3px" />Recipe / History
          </div>
          <div
            @click="loaderTab = 'restaurant'"
            style="padding:5px 12px 7px;font-size:11px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;user-select:none;color:#757575"
            :style="loaderTab === 'restaurant' ? 'border-color:#2e7d32;color:#2e7d32' : ''"
          >
            <i class="fas fa-utensils" style="font-size:10px;margin-right:3px" />Restaurant
          </div>
        </div>

        <!-- Recipe / History tab -->
        <div v-if="loaderTab === 'recipe'" ref="recipeSearchWrap">
          <v-text-field
            v-model="recipeSearch"
            label="Search recipes &amp; history"
            density="compact"
            variant="outlined"
            hide-details
            placeholder="e.g. chia pudding, cabbage noodles"
            clearable
            @input="onRecipeInput"
            @keydown.down.prevent="moveRecipeAC(1)"
            @keydown.up.prevent="moveRecipeAC(-1)"
            @keydown.enter.prevent="selectRecipeAC"
            @keydown.esc="showRecipeAC = false"
            @blur="_closeRecipeACDelayed"
          >
            <template #prepend-inner>
              <v-icon icon="fas fa-layer-group" size="x-small" color="green-darken-2" class="mr-1 mt-1" />
            </template>
          </v-text-field>
          <!-- Recipe autocomplete — teleported to body to escape any overflow:hidden parents -->
          <Teleport to="body">
            <div
              v-if="showRecipeAC && recipeAC.length"
              style="position:fixed;z-index:9999;background:#fff;border:1px solid #e0e0e0;border-radius:4px;box-shadow:0 4px 16px rgba(0,0,0,0.18);max-height:280px;overflow-y:auto"
              :style="recipeACStyle"
            >
              <div
                v-for="(r, j) in recipeAC"
                :key="j"
                class="px-3 py-2"
                :style="{ background: recipeACIdx === j ? '#f5f5f5' : '#fff', cursor: 'pointer', borderBottom: '1px solid #f5f5f5', minHeight: '48px' }"
                @mousedown.prevent="applyRecipe(r)"
              >
                <div class="d-flex align-center gap-2 mb-1">
                  <v-icon v-if="r._type === 'saved'" icon="fas fa-bookmark" size="x-small" color="green-darken-2" />
                  <v-icon v-else icon="fas fa-clock-rotate-left" size="x-small" color="grey" />
                  <span class="text-body-2 font-weight-medium">{{ r.name }}</span>
                </div>
                <div class="text-caption text-grey">
                  <template v-if="r._type === 'saved'">
                    {{ (r.items || []).length }} ingredient{{ (r.items || []).length !== 1 ? 's' : '' }} · saved {{ r.saved_at }}
                  </template>
                  <template v-else>
                    {{ r.date }} · {{ r.kcal_estimate }} kcal · {{ (r.components || []).length }} items
                  </template>
                </div>
              </div>
            </div>
          </Teleport>
        </div>

        <!-- Restaurant tab -->
        <div v-if="loaderTab === 'restaurant'">

          <!-- Step 1: Search for restaurant -->
          <template v-if="!selectedRestaurant">
            <div class="d-flex align-center mb-2" style="gap:6px">
              <i class="fas fa-location-dot" style="font-size:10px;color:#9e9e9e;flex-shrink:0" />
              <input
                v-model="restaurantLocation"
                placeholder="City, State"
                style="font-size:11px;color:#757575;border:none;outline:none;background:transparent;flex:1;min-width:0"
              />
            </div>
            <div class="d-flex gap-2">
              <v-text-field
                v-model="restaurantQuery"
                label="Restaurant name"
                density="compact"
                variant="outlined"
                hide-details
                placeholder="e.g. Genki Ya, Chipotle"
                class="flex-grow-1"
                :disabled="restaurantSearching"
                @keyup.enter="searchRestaurant"
              />
              <v-btn
                color="green-darken-2"
                variant="flat"
                size="default"
                :loading="restaurantSearching"
                :disabled="!restaurantQuery.trim() || restaurantSearching"
                @click="searchRestaurant"
              >
                <v-icon icon="fas fa-search" size="small" />
              </v-btn>
            </div>
            <v-alert v-if="restaurantSearchError && !restaurantSearching" type="warning" density="compact" variant="tonal" class="mt-2 mb-0">
              {{ restaurantSearchError }}
            </v-alert>
            <div v-if="restaurantCandidates.length" class="mt-2">
              <div class="text-caption font-weight-medium text-grey-darken-2 mb-1">Select the right one</div>
              <div
                v-for="(c, k) in restaurantCandidates"
                :key="k"
                class="d-flex align-center pa-2 mb-1 rounded"
                style="background:#f5f5f5;cursor:pointer"
                @click="selectRestaurant(c)"
              >
                <div class="flex-grow-1">
                  <div class="text-body-2 font-weight-medium">{{ c.name }}</div>
                  <div v-if="c.address" class="text-caption text-grey">{{ c.address }}</div>
                  <div v-if="c.notes" class="text-caption" style="color:#bdbdbd;font-style:italic">{{ c.notes }}</div>
                </div>
                <v-icon icon="fas fa-chevron-right" size="x-small" color="grey" class="ml-2 flex-shrink-0" />
              </div>
            </div>
          </template>

          <!-- Step 2: Add menu items -->
          <template v-else>
            <div class="d-flex align-center mb-2" style="gap:6px;flex-wrap:wrap">
              <v-chip
                color="green-darken-2"
                variant="tonal"
                size="small"
                closable
                @click:close="clearRestaurant"
              >
                <v-icon start icon="fas fa-utensils" size="x-small" />
                {{ selectedRestaurant.name }}
              </v-chip>
              <span v-if="selectedRestaurant.address" class="text-caption text-grey" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:200px">
                {{ selectedRestaurant.address }}
              </span>
            </div>
            <div class="d-flex gap-2" ref="restaurantItemWrap">
              <v-text-field
                v-model="restaurantItemQuery"
                label="Menu item"
                density="compact"
                variant="outlined"
                hide-details
                placeholder="e.g. Spicy tuna roll"
                class="flex-grow-1"
                @input="onRestaurantItemInput"
                @keyup.enter="addRestaurantComponent"
                @blur="_closeRestaurantItemACDelayed"
                @keydown.down.prevent="moveRestaurantItemAC(1)"
                @keydown.up.prevent="moveRestaurantItemAC(-1)"
              />
              <v-btn
                color="green-darken-2"
                variant="flat"
                size="default"
                :disabled="!restaurantItemQuery.trim()"
                @click="addRestaurantComponent"
              >
                <v-icon icon="fas fa-plus" size="small" />
              </v-btn>
            </div>
            <Teleport to="body" v-if="showRestaurantItemAC && restaurantItemHints.length">
              <div
                :style="restaurantItemACStyle"
                style="position:fixed;z-index:9999;background:white;border:1px solid #e0e0e0;border-radius:8px;box-shadow:0 4px 16px rgba(0,0,0,0.12);max-height:200px;overflow-y:auto"
              >
                <div
                  v-for="(hint, k) in restaurantItemHints"
                  :key="k"
                  class="d-flex align-center px-3 py-2"
                  style="cursor:pointer;border-bottom:1px solid #f5f5f5"
                  :style="restaurantItemACIdx === k ? 'background:#f5f5f5' : ''"
                  @mousedown.prevent="applyRestaurantHint(hint)"
                >
                  <div class="text-body-2 flex-grow-1">{{ hint.itemName }}</div>
                  <v-chip size="x-small" color="orange" label class="ml-2">hist</v-chip>
                </div>
              </div>
            </Teleport>
          </template>

        </div>
      </v-card-text>
    </v-card>

    <!-- Food items -->
    <v-card v-for="(item, i) in items" :key="i" class="mb-3" rounded="lg" elevation="1" style="overflow:visible">
      <v-card-text>

        <!-- Description field with autocomplete + camera + remove -->
        <div class="mb-3">
          <v-row dense align="center">
            <v-col>
              <!-- Wrapper div used for dropdown positioning -->
              <div :ref="el => { if (el) acRefs[i] = el; else delete acRefs[i] }">
                <v-text-field
                  v-model="item.description"
                  :label="item.resolvedProduct ? item.resolvedProduct.name : 'What did you eat?'"
                  density="compact"
                  variant="outlined"
                  hide-details
                  :placeholder="item.resolvedProduct ? '' : 'e.g. plain bagel with cream cheese'"
                  :readonly="!!item.resolvedProduct"
                  @input="onDescriptionInput(i)"
                  @keydown.down.prevent="moveAutocomplete(i, 1)"
                  @keydown.up.prevent="moveAutocomplete(i, -1)"
                  @keydown.enter.prevent="selectAutocomplete(i)"
                  @keydown.esc="closeAutocomplete(i)"
                  @blur="_closeAutocompleteDelayed(i)"
                >
                  <template v-if="item.resolvedProduct" #append-inner>
                    <v-btn icon variant="text" size="x-small" color="grey" title="Clear product" @click="clearResolved(item)">
                      <v-icon icon="fas fa-times" size="x-small" />
                    </v-btn>
                  </template>
                </v-text-field>
              </div>
              <!-- Ingredient autocomplete — teleported to body -->
              <Teleport to="body">
                <div
                  v-if="item.showAutocomplete && item.autocomplete.length"
                  style="position:fixed;z-index:9999;background:#fff;border:1px solid #e0e0e0;border-radius:4px;box-shadow:0 4px 16px rgba(0,0,0,0.18);max-height:240px;overflow-y:auto"
                  :style="item.acDropStyle"
                >
                  <div
                    v-for="(r, j) in item.autocomplete"
                    :key="j"
                    class="px-3 py-2"
                    :style="{ background: item.autocompleteIdx === j ? '#f5f5f5' : '#fff', cursor: 'pointer', borderBottom: '1px solid #f5f5f5', minHeight: '44px' }"
                    @mousedown.prevent="applyAutocomplete(item, r)"
                  >
                    <div class="text-body-2">{{ r.name }}</div>
                    <div class="text-caption text-grey">
                      {{ Number(r.quantity_g).toFixed(1) }}g
                      <template v-if="r.nutrition_per_100g">· {{ Math.round((r.nutrition_per_100g.calories_kcal || 0) * r.quantity_g / 100) }} kcal</template>
                      <v-chip v-if="r.barcode" size="x-small" color="blue" variant="tonal" class="ml-1">barcode</v-chip>
                      <v-chip size="x-small" :color="r.source === 'openfoodfacts' ? 'green' : 'orange'" variant="tonal" class="ml-1">{{ r.source === 'openfoodfacts' ? 'OFf' : (r.source || 'usda') }}</v-chip>
                    </div>
                  </div>
                </div>
              </Teleport>
            </v-col>
            <v-col cols="auto" style="padding-left:4px">
              <v-btn icon variant="text" color="green-darken-2" size="small" title="Scan barcode" @click="openScanner(item)">
                <v-icon icon="fas fa-camera" size="small" />
              </v-btn>
            </v-col>
            <v-col cols="auto" style="padding-left:0">
              <v-btn icon variant="text" color="grey" size="small" @click="items.splice(i, 1)">
                <v-icon icon="fas fa-times" size="small" />
              </v-btn>
            </v-col>
          </v-row>
        </div>

        <!-- Lookup error -->
        <v-alert v-if="item.lookupError" type="warning" density="compact" class="mb-3 mt-n1" variant="tonal">
          {{ item.lookupError }}
        </v-alert>

        <!-- Loading -->
        <div v-if="item.loading" class="text-center py-2 mb-2">
          <v-progress-circular indeterminate size="24" color="green-darken-2" />
        </div>

        <!-- Resolved OFf product -->
        <div v-if="item.resolvedProduct" class="mb-3">
          <div class="d-flex align-start gap-3 mb-2">
            <img
              v-if="item.resolvedProduct.images && item.resolvedProduct.images.front"
              :src="item.resolvedProduct.images.front"
              style="width:64px;height:64px;object-fit:contain;border-radius:6px;background:#f5f5f5;flex-shrink:0;cursor:pointer"
              @click="lightboxUrl = item.resolvedProduct.images.front"
            />
            <div style="min-width:0">
              <div class="d-flex align-center flex-wrap gap-1 mb-1">
                <v-chip :color="item.resolvedSource === 'history' ? 'orange' : item.resolvedSource === 'restaurant' ? 'teal' : 'green-darken-2'" size="x-small" label>{{ item.resolvedSource === 'history' ? 'hist' : item.resolvedSource === 'restaurant' ? 'rest' : 'OFf' }}</v-chip>
                <span class="font-weight-medium text-body-2">{{ item.resolvedProduct.name }}</span>
              </div>
              <div v-if="item.resolvedProduct.brand" class="text-caption text-grey mb-1">{{ item.resolvedProduct.brand }}<span v-if="item.resolvedProduct.serving_size" class="ml-2">· {{ item.resolvedProduct.serving_size }}</span></div>
              <div class="d-flex flex-wrap gap-1">
                <v-chip v-if="item.resolvedProduct.nutriscore_grade" size="x-small" :color="nutriscoreColor(item.resolvedProduct.nutriscore_grade)" variant="flat" style="color:#fff;font-weight:700">NutriScore {{ item.resolvedProduct.nutriscore_grade.toUpperCase() }}</v-chip>
                <v-chip v-if="item.resolvedProduct.nova_group" size="x-small" :color="novaColor(item.resolvedProduct.nova_group)" variant="tonal" :title="novaLabel(item.resolvedProduct.nova_group)">NOVA {{ item.resolvedProduct.nova_group }}</v-chip>
                <v-chip v-if="item.resolvedProduct.ecoscore_grade && item.resolvedProduct.ecoscore_grade !== 'unknown'" size="x-small" color="blue-grey" variant="tonal">Eco {{ item.resolvedProduct.ecoscore_grade.toUpperCase() }}</v-chip>
              </div>
            </div>
          </div>

          <div v-if="(item.resolvedProduct.analysis_tags || []).length || (item.resolvedProduct.allergens || []).length" class="d-flex flex-wrap gap-1 mb-2">
            <v-chip v-for="tag in item.resolvedProduct.analysis_tags || []" :key="tag" size="x-small" :color="analysisTagColor(tag)" variant="tonal">{{ formatTag(tag) }}</v-chip>
            <v-chip v-for="allergen in item.resolvedProduct.allergens || []" :key="allergen" size="x-small" color="deep-orange" variant="tonal">⚠ {{ allergen }}</v-chip>
          </div>

          <div class="text-caption pa-2 bg-grey-lighten-4 rounded mb-2">
            <div class="font-weight-medium mb-1 text-grey-darken-2">Per 100g</div>
            <div class="mb-1">
              <span class="text-green-darken-2 font-weight-medium">{{ fmt0(item.resolvedProduct.per100g.calories_kcal) }} kcal</span>
              <span class="text-grey-darken-1 ml-1">· P {{ fmt1(item.resolvedProduct.per100g.protein_g) }}g · F {{ fmt1(item.resolvedProduct.per100g.total_fat_g) }}g · C {{ fmt1(item.resolvedProduct.per100g.total_carbohydrate_g) }}g</span>
            </div>
            <div v-if="item.resolvedProduct.per100g.saturated_fat_g != null || item.resolvedProduct.per100g.trans_fat_g != null" class="text-grey mb-1">
              <template v-if="item.resolvedProduct.per100g.saturated_fat_g != null">Sat {{ fmt1(item.resolvedProduct.per100g.saturated_fat_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.monounsaturated_fat_g != null"> · Mono {{ fmt1(item.resolvedProduct.per100g.monounsaturated_fat_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.polyunsaturated_fat_g != null"> · Poly {{ fmt1(item.resolvedProduct.per100g.polyunsaturated_fat_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.trans_fat_g != null"> · Trans {{ fmt1(item.resolvedProduct.per100g.trans_fat_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.cholesterol_mg != null"> · Chol {{ fmt0(item.resolvedProduct.per100g.cholesterol_mg) }}mg</template>
            </div>
            <div v-if="item.resolvedProduct.per100g.fiber_g != null || item.resolvedProduct.per100g.sugar_g != null || item.resolvedProduct.per100g.starch_g != null" class="text-grey mb-1">
              <template v-if="item.resolvedProduct.per100g.fiber_g != null">Fiber {{ fmt1(item.resolvedProduct.per100g.fiber_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.starch_g != null"><template v-if="item.resolvedProduct.per100g.fiber_g != null"> · </template>Starch {{ fmt1(item.resolvedProduct.per100g.starch_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.sugar_g != null"> · Sugar {{ fmt1(item.resolvedProduct.per100g.sugar_g) }}g</template>
              <template v-if="item.resolvedProduct.per100g.added_sugar_g != null"> ({{ fmt1(item.resolvedProduct.per100g.added_sugar_g) }}g added)</template>
            </div>
            <div v-if="item.resolvedProduct.per100g.sodium_mg != null" class="text-grey mb-1">
              Na {{ fmt0(item.resolvedProduct.per100g.sodium_mg) }}mg
              <template v-if="item.resolvedProduct.per100g.potassium_mg != null"> · K {{ fmt0(item.resolvedProduct.per100g.potassium_mg) }}mg</template>
              <template v-if="item.resolvedProduct.per100g.calcium_mg != null"> · Ca {{ fmt0(item.resolvedProduct.per100g.calcium_mg) }}mg</template>
              <template v-if="item.resolvedProduct.per100g.iron_mg != null"> · Fe {{ fmt2(item.resolvedProduct.per100g.iron_mg) }}mg</template>
              <template v-if="item.resolvedProduct.per100g.magnesium_mg != null"> · Mg {{ fmt0(item.resolvedProduct.per100g.magnesium_mg) }}mg</template>
              <template v-if="item.resolvedProduct.per100g.zinc_mg != null"> · Zn {{ fmt1(item.resolvedProduct.per100g.zinc_mg) }}mg</template>
            </div>
            <div v-if="item.resolvedProduct.per100g.vitamin_c_mg != null || item.resolvedProduct.per100g.vitamin_d_ug != null || item.resolvedProduct.per100g.vitamin_b12_ug != null || item.resolvedProduct.per100g.folate_ug != null" class="text-grey">
              <template v-if="item.resolvedProduct.per100g.vitamin_a_ug != null">Vit A {{ fmt0(item.resolvedProduct.per100g.vitamin_a_ug) }}µg</template>
              <template v-if="item.resolvedProduct.per100g.vitamin_c_mg != null"><template v-if="item.resolvedProduct.per100g.vitamin_a_ug != null"> · </template>Vit C {{ fmt1(item.resolvedProduct.per100g.vitamin_c_mg) }}mg</template>
              <template v-if="item.resolvedProduct.per100g.vitamin_d_ug != null"> · Vit D {{ fmt1(item.resolvedProduct.per100g.vitamin_d_ug) }}µg</template>
              <template v-if="item.resolvedProduct.per100g.vitamin_b12_ug != null"> · B12 {{ fmt1(item.resolvedProduct.per100g.vitamin_b12_ug) }}µg</template>
              <template v-if="item.resolvedProduct.per100g.folate_ug != null"> · Folate {{ fmt0(item.resolvedProduct.per100g.folate_ug) }}µg</template>
            </div>
          </div>

          <v-expansion-panels v-if="(item.resolvedProduct.ingredients || []).length" flat class="mb-2" style="border:1px solid #e0e0e0;border-radius:8px">
            <v-expansion-panel>
              <v-expansion-panel-title class="text-caption font-weight-medium py-2 px-3">Ingredients ({{ item.resolvedProduct.ingredients.length }})</v-expansion-panel-title>
              <v-expansion-panel-text class="px-1">
                <div v-for="(ing, j) in item.resolvedProduct.ingredients" :key="j" class="d-flex align-center py-1 px-2" style="border-bottom:1px solid #f5f5f5">
                  <span class="text-caption flex-grow-1">{{ ing.text }}</span>
                  <span v-if="ing.percent != null" class="text-caption text-grey ml-2 flex-shrink-0">~{{ ing.percent }}%</span>
                  <v-chip v-if="ing.vegan === 'yes'" size="x-small" color="green" variant="tonal" class="ml-1">V</v-chip>
                  <v-chip v-else-if="ing.vegan === 'no'" size="x-small" color="red" variant="tonal" class="ml-1">✕V</v-chip>
                </div>
              </v-expansion-panel-text>
            </v-expansion-panel>
          </v-expansion-panels>

          <div v-if="item.resolvedProduct.images && (item.resolvedProduct.images.ingredients || item.resolvedProduct.images.nutrition)" class="d-flex align-start gap-3 mt-1">
            <div v-if="item.resolvedProduct.images.ingredients" class="text-center" style="cursor:pointer" @click="lightboxUrl = item.resolvedProduct.images.ingredients">
              <img :src="item.resolvedProduct.images.ingredients" style="height:52px;border-radius:4px;border:1px solid #ddd;display:block" />
              <div class="text-caption text-grey mt-1">Ingredients</div>
            </div>
            <div v-if="item.resolvedProduct.images.nutrition" class="text-center" style="cursor:pointer" @click="lightboxUrl = item.resolvedProduct.images.nutrition">
              <img :src="item.resolvedProduct.images.nutrition" style="height:52px;border-radius:4px;border:1px solid #ddd;display:block" />
              <div class="text-caption text-grey mt-1">Nutrition</div>
            </div>
            <div v-if="!item.resolvedProduct.images.ingredients || !item.resolvedProduct.images.nutrition" class="text-caption text-grey align-self-center">
              Missing photos? <a :href="`https://world.openfoodfacts.org/product/${item.barcode}`" target="_blank" class="text-green-darken-2">Contribute on OFf</a>
            </div>
          </div>
        </div>

        <!-- Quantity + unit -->
        <v-row dense align="center">
          <v-col cols="4">
            <v-text-field v-model.number="item.quantity" label="Amount" type="number" min="0" step="0.25" density="compact" variant="outlined" hide-details />
          </v-col>
          <v-col cols="5">
            <v-select v-model="item.unit" :items="availableUnits(item)" label="Unit" density="compact" variant="outlined" hide-details />
          </v-col>
          <v-col cols="3">
            <div class="text-caption text-grey text-center">
              <template v-if="estimateGrams(item) !== null">≈ {{ Math.round(estimateGrams(item)) }}g</template>
              <template v-else><span class="text-error">unit?</span></template>
            </div>
          </v-col>
        </v-row>

        <!-- Item total -->
        <div v-if="itemTotal(item)" class="mt-2 pa-2 bg-green-lighten-5 rounded text-caption">
          <span class="font-weight-medium text-green-darken-2">{{ itemTotal(item).calories.toFixed(0) }} kcal</span>
          <span class="ml-2 text-grey-darken-1">P {{ itemTotal(item).protein.toFixed(1) }}g · F {{ itemTotal(item).fat.toFixed(1) }}g · C {{ itemTotal(item).carbs.toFixed(1) }}g</span>
        </div>
      </v-card-text>
    </v-card>

    <v-btn variant="tonal" color="green-darken-2" class="mb-4" prepend-icon="fas fa-plus" @click="addItem">Add ingredient</v-btn>

    <!-- Running total -->
    <v-card rounded="lg" elevation="1" class="mb-4">
      <v-card-title class="text-subtitle-2 pb-0">Running total</v-card-title>
      <v-card-text>
        <v-row dense class="text-center">
          <v-col><div class="text-h6 text-green-darken-2">{{ runningTotal.calories.toFixed(0) }}</div><div class="text-caption text-grey">kcal</div></v-col>
          <v-col><div class="text-h6">{{ runningTotal.protein.toFixed(1) }}</div><div class="text-caption text-grey">protein g</div></v-col>
          <v-col><div class="text-h6">{{ runningTotal.fat.toFixed(1) }}</div><div class="text-caption text-grey">fat g</div></v-col>
          <v-col><div class="text-h6">{{ runningTotal.carbs.toFixed(1) }}</div><div class="text-caption text-grey">carbs g</div></v-col>
        </v-row>
        <div class="mt-2" style="height:8px;border-radius:4px;background:#eee;overflow:hidden">
          <div style="height:100%;display:flex">
            <div :style="{ width: proteinPct + '%', background: '#4CAF50' }" />
            <div :style="{ width: fatPct + '%', background: '#FF9800' }" />
            <div :style="{ width: carbsPct + '%', background: '#2196F3' }" />
          </div>
        </div>
        <div class="d-flex text-caption mt-1">
          <span class="mr-2"><span style="color:#4CAF50">■</span> protein</span>
          <span class="mr-2"><span style="color:#FF9800">■</span> fat</span>
          <span><span style="color:#2196F3">■</span> carbs</span>
        </div>
      </v-card-text>
      <v-card-actions>
        <v-btn
          icon variant="text" color="green-darken-2"
          title="Save as recipe"
          :disabled="!saveableItems.length"
          @click="saveRecipeDialog = true"
        >
          <v-icon icon="fas fa-bookmark" size="small" />
        </v-btn>
        <v-spacer />
        <v-btn variant="outlined" color="grey" @click="showPreview = true">Preview</v-btn>
        <v-btn color="green-darken-2" variant="flat" @click="showPreview = true">Submit</v-btn>
      </v-card-actions>
    </v-card>

    <!-- Preview / submit dialog -->
    <v-dialog v-model="showPreview" max-width="600">
      <v-card rounded="lg">
        <v-card-title>Entry preview</v-card-title>
        <v-card-text>
          <div class="text-caption text-grey mb-2">{{ date }} {{ time }}</div>
          <pre class="pa-3 rounded bg-grey-lighten-4" style="white-space:pre-wrap;font-size:13px;font-family:monospace">{{ formattedEntry }}</pre>
          <v-divider class="my-3" />
          <div class="text-caption text-grey mb-1">Submit to endpoint (optional)</div>
          <v-text-field v-model="endpointUrl" label="API endpoint URL" density="compact" variant="outlined" hide-details placeholder="https://…/entry" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showPreview = false">Close</v-btn>
          <v-btn color="green-darken-2" variant="flat" :disabled="!endpointUrl" :loading="submitting" @click="postEntry">Send</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Save recipe dialog -->
    <v-dialog v-model="saveRecipeDialog" max-width="400">
      <v-card rounded="lg">
        <v-card-title>Save as recipe</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="saveRecipeName"
            label="Recipe name"
            density="compact"
            variant="outlined"
            placeholder="e.g. Chia Seed Pudding"
            hide-details
            class="mb-2"
            @keyup.enter="saveRecipe"
          />
          <div class="text-caption text-grey">
            {{ saveableItems.length }} ingredient{{ saveableItems.length !== 1 ? 's' : '' }} will be saved
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="saveRecipeDialog = false; saveRecipeName = ''">Cancel</v-btn>
          <v-btn color="green-darken-2" variant="flat" :disabled="!saveRecipeName.trim() || !saveableItems.length" :loading="savingRecipe" @click="saveRecipe">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Image lightbox -->
    <v-dialog v-model="lightboxOpen" max-width="700">
      <v-card>
        <v-card-text class="pa-2 text-center">
          <img :src="lightboxUrl" style="max-width:100%;max-height:80vh;object-fit:contain" />
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="lightboxUrl = null">Close</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Barcode scanner dialog -->
    <v-dialog v-model="scannerOpen" max-width="480">
      <v-card rounded="lg" style="overflow:hidden">
        <v-card-title class="d-flex align-center py-2 px-4">
          <v-icon icon="fas fa-barcode" size="small" class="mr-2" color="green-darken-2" />
          Scan barcode
          <v-spacer />
          <v-btn icon variant="text" size="small" @click="scannerOpen = false"><v-icon icon="fas fa-times" /></v-btn>
        </v-card-title>
        <div style="position:relative;background:#000;line-height:0;min-height:180px">
          <video ref="scannerVideo" style="width:100%;max-height:60vw;object-fit:cover;display:block" playsinline muted />
          <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none">
            <div style="position:relative;width:72%;height:40%">
              <div style="width:100%;height:100%;border:2px solid #4CAF50;border-radius:4px;box-shadow:0 0 0 999px rgba(0,0,0,0.45)">
                <div style="position:absolute;top:-3px;left:-3px;width:18px;height:18px;border-top:4px solid #4CAF50;border-left:4px solid #4CAF50;border-radius:3px 0 0 0"></div>
                <div style="position:absolute;top:-3px;right:-3px;width:18px;height:18px;border-top:4px solid #4CAF50;border-right:4px solid #4CAF50;border-radius:0 3px 0 0"></div>
                <div style="position:absolute;bottom:-3px;left:-3px;width:18px;height:18px;border-bottom:4px solid #4CAF50;border-left:4px solid #4CAF50;border-radius:0 0 0 3px"></div>
                <div style="position:absolute;bottom:-3px;right:-3px;width:18px;height:18px;border-bottom:4px solid #4CAF50;border-right:4px solid #4CAF50;border-radius:0 0 3px 0"></div>
              </div>
            </div>
          </div>
          <div style="position:absolute;bottom:0;left:0;right:0;padding:6px;text-align:center;background:rgba(0,0,0,0.55)">
            <span v-if="scannerError" style="color:#ef5350;font-size:13px">{{ scannerError }}</span>
            <span v-else style="color:rgba(255,255,255,0.85);font-size:12px">Point camera at barcode</span>
          </div>
        </div>
        <v-card-text class="pt-3 pb-3">
          <div class="text-caption text-grey mb-2">Or enter barcode manually:</div>
          <v-row dense align="center">
            <v-col>
              <v-text-field
                v-model="scannerManualBarcode"
                label="Barcode number"
                density="compact"
                variant="outlined"
                hide-details
                placeholder="e.g. 0014100074724"
                type="number"
                @keyup.enter="submitManualBarcode"
              />
            </v-col>
            <v-col cols="auto">
              <v-btn color="green-darken-2" size="small" :disabled="!scannerManualBarcode" @click="submitManualBarcode">Look up</v-btn>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000">{{ snackbar.text }}</v-snackbar>
  </v-container>
</template>

<script>
const UNITS = ["g", "oz", "tbsp", "tsp", "cup", "fl oz", "ml", "serving", "piece", "slice"];
const NUTRISCORE_COLORS = { a: "#038141", b: "#85BB2F", c: "#FECB02", d: "#EE8100", e: "#E63E11" };
const NOVA_COLORS = { 1: "green", 2: "light-green", 3: "orange", 4: "deep-orange" };
const NOVA_LABELS = { 1: "Unprocessed / minimally processed", 2: "Culinary ingredients", 3: "Processed food", 4: "Ultra-processed food" };
const ANALYSIS_TAG_COLORS = { "palm-oil": "orange", "may-contain-traces-of-palm-oil": "amber", "non-vegan": "red", vegan: "green", "non-vegetarian": "red", vegetarian: "light-green", "vegetarian-status-unknown": "grey", "vegan-status-unknown": "grey" };

const EMPTY_PER100G = {
  calories_kcal: null, protein_g: null, total_fat_g: null, saturated_fat_g: null,
  monounsaturated_fat_g: null, polyunsaturated_fat_g: null, omega3_g: null, trans_fat_g: null,
  total_carbohydrate_g: null, fiber_g: null, sugar_g: null, added_sugar_g: null, starch_g: null,
  cholesterol_mg: null, sodium_mg: null, potassium_mg: null, calcium_mg: null, iron_mg: null,
  magnesium_mg: null, zinc_mg: null, vitamin_a_ug: null, vitamin_c_mg: null, vitamin_d_ug: null,
  vitamin_b12_ug: null, folate_ug: null,
};

function s3Base() {
  const v = (typeof window !== "undefined" && window.CTBUS_S3) || "";
  return v === "CTBUS_S3_PLACEHOLDER" ? "" : v;
}
function apiBase() {
  const v = (typeof window !== "undefined" && window.CTBUS_API) || "";
  return v === "CTBUS_API_PLACEHOLDER" ? "/entry" : v;
}
function nowDate() { return new Date().toLocaleDateString("en-CA"); }
function nowTime() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function newItem() {
  return {
    description: "", barcode: "", quantity: 1, unit: "serving",
    resolvedProduct: null, resolvedSource: null,
    loading: false, lookupError: null,
    autocomplete: [], showAutocomplete: false, autocompleteIdx: -1,
    acDropStyle: {},
  };
}

export default {
  name: "EntryView",
  data() {
    return {
      date: nowDate(),
      time: nowTime(),
      todayData: null,
      items: [newItem()],
      historyComponents: [],
      historyEntries: [],
      savedRecipes: [],
      // Loader tab state
      loaderTab: "recipe",
      // Recipe search
      recipeSearch: "",
      recipeAC: [],
      showRecipeAC: false,
      recipeACIdx: -1,
      recipeACStyle: {},
      acRefs: {},
      // Restaurant search
      restaurantQuery: "",
      restaurantLocation: "",
      restaurantSearching: false,
      restaurantCandidates: [],
      restaurantSearchError: null,
      selectedRestaurant: null,
      restaurantItemQuery: "",
      restaurantItemHints: [],
      restaurantItemACIdx: -1,
      showRestaurantItemAC: false,
      restaurantItemACStyle: {},
      // Save recipe
      saveRecipeDialog: false,
      saveRecipeName: "",
      savingRecipe: false,
      // UI state
      showPreview: false,
      lightboxUrl: null,
      endpointUrl: apiBase(),
      submitting: false,
      snackbar: { show: false, text: "", color: "success" },
      scannerOpen: false,
      scannerItem: null,
      scannerError: null,
      scannerManualBarcode: "",
      _codeReader: null,
    };
  },
  async created() {
    // Recipe pre-loaded from Recipes page
    const pending = window._ctbus_pending_recipe;
    if (pending) {
      window._ctbus_pending_recipe = null;
      const newItems = (pending.items || []).map(c => this._buildItem(c));
      if (newItems.length) this.items = newItems;
    }
    try {
      const resp = await fetch(`${s3Base()}/diet/${nowDate()}.json`, { cache: "no-cache" });
      if (resp.ok) this.todayData = await resp.json();
    } catch (e) { /* no today data yet */ }
    this._loadHistory();
    this._loadSavedRecipes();
    // Get rough location for restaurant search
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(async pos => {
        try {
          const { latitude, longitude } = pos.coords;
          const resp = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}`, {
            headers: { "User-Agent": "ctbus-health/1.0" },
          });
          if (resp.ok) {
            const geo = await resp.json();
            const city = geo.address?.city || geo.address?.town || geo.address?.village || "";
            const state = geo.address?.state || "";
            if (city) this.restaurantLocation = state ? `${city}, ${state}` : city;
          }
        } catch {}
      }, () => {}, { timeout: 5000, maximumAge: 300000 });
    }
  },
  watch: {
    scannerOpen(open) {
      if (open) {
        this.scannerManualBarcode = "";
        setTimeout(() => this._startScanner(), 250);
      } else {
        this._stopScanner();
      }
    },
  },
  computed: {
    todayTotals() {
      if (!this.todayData) return null;
      let kcal = 0, protein = 0, fat = 0, carbs = 0;
      for (const entry of this.todayData.entries || []) {
        for (const comp of entry.components || []) {
          const n = comp.nutrition_total || {};
          kcal += n.calories_kcal || 0;
          protein += n.protein_g || 0;
          fat += n.total_fat_g || 0;
          carbs += n.total_carbohydrate_g || 0;
        }
      }
      return { kcal, protein, fat, carbs };
    },
    todayEntryCount() { return this.todayData?.entries?.length ?? 0; },
    lightboxOpen: {
      get() { return !!this.lightboxUrl; },
      set(v) { if (!v) this.lightboxUrl = null; },
    },
    saveableItems() {
      return this.items.filter(it => it.resolvedProduct && it.resolvedProduct.name);
    },
    runningTotal() {
      return this.items.reduce((acc, item) => {
        const t = this.itemTotal(item);
        if (!t) return acc;
        return { calories: acc.calories + t.calories, protein: acc.protein + t.protein, fat: acc.fat + t.fat, carbs: acc.carbs + t.carbs };
      }, { calories: 0, protein: 0, fat: 0, carbs: 0 });
    },
    totalMacroG() {
      const t = this.runningTotal;
      return t.protein * 4 + t.fat * 9 + t.carbs * 4;
    },
    proteinPct() { return this.totalMacroG ? Math.min(100, (this.runningTotal.protein * 4 / this.totalMacroG) * 100) : 0; },
    fatPct()     { return this.totalMacroG ? Math.min(100, (this.runningTotal.fat * 9 / this.totalMacroG) * 100) : 0; },
    carbsPct()   { return this.totalMacroG ? Math.min(100 - this.proteinPct - this.fatPct, (this.runningTotal.carbs * 4 / this.totalMacroG) * 100) : 0; },
    formattedEntry() {
      const lines = [`${this.date} ${this.time}`, ""];
      for (const item of this.items) {
        const grams = this.estimateGrams(item);
        const name = item.resolvedProduct ? item.resolvedProduct.name : item.description;
        if (!name) continue;
        const gramsStr = grams !== null ? ` (~${Math.round(grams)}g)` : "";
        const barcodeStr = item.barcode ? ` [barcode:${item.barcode}]` : "";
        lines.push(`${item.quantity} ${item.unit} ${name}${gramsStr}${barcodeStr}`);
      }
      return lines.join("\n");
    },
  },
  methods: {
    // ── History loading ──
    async _loadHistory() {
      try {
        const idxResp = await fetch(`${s3Base()}/diet/index.json`, { cache: "no-cache" });
        if (!idxResp.ok) return;
        const dates = await idxResp.json();
        const results = await Promise.all(
          dates.slice(0, 30).map(date =>
            fetch(`${s3Base()}/diet/${date}.json`, { cache: "no-cache" }).then(r => r.ok ? r.json() : null).catch(() => null)
          )
        );
        const seen = new Map();
        const entries = [];
        for (const dayData of results) {
          if (!dayData) continue;
          for (const entry of dayData.entries || []) {
            const comps = entry.components || [];
            for (const comp of comps) {
              if (comp.name && !seen.has(comp.name)) seen.set(comp.name, { ...comp, date: dayData.date });
            }
            if (comps.length >= 2) {
              const names = comps.map(c => c.name).filter(Boolean);
              const kcal = comps.reduce((s, c) => s + (c.nutrition_total?.calories_kcal || 0), 0);
              entries.push({
                name: names.slice(0, 3).join(", ") + (names.length > 3 ? ` +${names.length - 3} more` : ""),
                date: dayData.date,
                timestamp: entry.timestamp,
                kcal_estimate: Math.round(kcal),
                components: comps,
                _type: "history_entry",
              });
            }
          }
        }
        this.historyComponents = Array.from(seen.values());
        this.historyEntries = entries;
      } catch (e) { /* history unavailable */ }
    },

    async _loadSavedRecipes() {
      try {
        const resp = await fetch(`${s3Base()}/diet/recipes.json`, { cache: "no-cache" });
        if (resp.ok) {
          const data = await resp.json();
          this.savedRecipes = data.map(r => ({ ...r, _type: "saved" }));
        }
      } catch (e) { /* no recipes yet */ }
    },

    // ── Recipe search ──
    onRecipeInput() {
      const q = (this.recipeSearch || "").trim().toLowerCase();
      if (q.length < 2) { this.recipeAC = []; this.showRecipeAC = false; return; }
      const words = q.split(/\s+/);
      const matches = (r) => {
        const text = [r.name || "", ...(r.items || r.components || []).map(c => c.name || "")].join(" ").toLowerCase();
        return words.every(w => text.includes(w));
      };
      const saved = this.savedRecipes.filter(matches).slice(0, 3);
      const hist = this.historyEntries.filter(matches).slice(0, 6 - saved.length);
      this.recipeAC = [...saved, ...hist];
      this.showRecipeAC = this.recipeAC.length > 0;
      this.recipeACIdx = -1;
      if (this.showRecipeAC && this.$refs.recipeSearchWrap) {
        const rect = this.$refs.recipeSearchWrap.getBoundingClientRect();
        this.recipeACStyle = { top: (rect.bottom + 2) + "px", left: rect.left + "px", width: rect.width + "px" };
      }
    },
    moveRecipeAC(dir) {
      if (!this.showRecipeAC) return;
      this.recipeACIdx = Math.max(-1, Math.min(this.recipeAC.length - 1, this.recipeACIdx + dir));
    },
    selectRecipeAC() {
      if (this.recipeACIdx >= 0 && this.recipeAC[this.recipeACIdx]) this.applyRecipe(this.recipeAC[this.recipeACIdx]);
    },
    _closeRecipeACDelayed() { setTimeout(() => { this.showRecipeAC = false; }, 160); },
    applyRecipe(recipe) {
      this.showRecipeAC = false;
      this.recipeSearch = "";
      this.recipeACIdx = -1;
      const sources = recipe._type === "saved" ? (recipe.items || []) : (recipe.components || []);
      const newItems = sources.map(c => this._buildItem(c));
      if (!newItems.length) return;
      const isDefault = this.items.length === 1 && !this.items[0].description && !this.items[0].resolvedProduct;
      this.items = isDefault ? newItems : [...this.items, ...newItems];
    },
    _buildItem(comp) {
      const item = newItem();
      item.description = comp.name || "";
      item.barcode = comp.barcode || "";
      if (comp.unit && comp.quantity != null) {
        item.quantity = comp.quantity;
        item.unit = comp.unit;
      } else {
        item.quantity = comp.quantity_g || 100;
        item.unit = "g";
      }
      item.resolvedSource = "history";
      if (comp.nutrition_per_100g) {
        const servingG = (comp.unit === "serving" && comp.quantity > 0)
          ? Math.round(comp.quantity_g / comp.quantity)
          : (comp.quantity_g || null);
        item.resolvedProduct = {
          name: comp.name || "", brand: "", serving_size: "",
          quantity_g: servingG, servings_per_container: null,
          nutriscore_grade: null, nova_group: null, ecoscore_grade: null,
          images: { front: null, ingredients: null, nutrition: null },
          allergens: [], analysis_tags: [], vitamins_tags: [], ingredients: [],
          per100g: { ...EMPTY_PER100G, ...comp.nutrition_per_100g },
        };
      }
      return item;
    },

    // ── Restaurant search ──
    async searchRestaurant() {
      if (!this.restaurantQuery.trim()) return;
      this.restaurantSearching = true;
      this.restaurantCandidates = [];
      this.restaurantSearchError = null;
      try {
        const client_id = crypto.randomUUID();
        const resp = await fetch(apiBase(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source: "restaurant_lookup",
            client_id,
            restaurant: this.restaurantQuery.trim(),
            location: this.restaurantLocation || "",
          }),
        });
        if (!resp.ok) {
          this.restaurantSearchError = `Search failed (${resp.status}). Please try again.`;
          return;
        }
        const result = await this._pollRestaurantLookup(client_id);
        if (result) {
          this.restaurantCandidates = result.candidates || [];
          if (!this.restaurantCandidates.length)
            this.restaurantSearchError = "No results found. Try a different name or location.";
        } else {
          this.restaurantSearchError = "Search timed out. Please try again.";
        }
      } catch (e) {
        this.restaurantSearchError = `Error: ${e.message}`;
      } finally {
        this.restaurantSearching = false;
      }
    },

    async _pollRestaurantLookup(clientId) {
      const url = `${s3Base()}/diet/restaurant_lookup/${clientId}.json`;
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const resp = await fetch(url);
          if (resp.ok) return await resp.json();
        } catch {}
      }
      return null;
    },

    selectRestaurant(c) {
      this.selectedRestaurant = c;
      this.restaurantCandidates = [];
      this.restaurantQuery = "";
      this.restaurantItemQuery = "";
      this.restaurantItemHints = [];
      this.showRestaurantItemAC = false;
    },

    clearRestaurant() {
      this.selectedRestaurant = null;
      this.restaurantCandidates = [];
      this.restaurantItemQuery = "";
      this.restaurantItemHints = [];
      this.showRestaurantItemAC = false;
    },

    onRestaurantItemInput() {
      const q = (this.restaurantItemQuery || "").trim().toLowerCase();
      if (q.length < 2) { this.restaurantItemHints = []; this.showRestaurantItemAC = false; return; }
      const rName = (this.selectedRestaurant?.name || "").toLowerCase();
      const words = q.split(/\s+/);
      this.restaurantItemHints = this.historyComponents
        .filter(c => {
          const n = c.name.toLowerCase();
          return n.includes(`from ${rName}`) && words.every(w => n.includes(w));
        })
        .slice(0, 6)
        .map(c => {
          const fromIdx = c.name.toLowerCase().indexOf(" from ");
          return { ...c, itemName: fromIdx >= 0 ? c.name.slice(0, fromIdx) : c.name };
        });
      this.restaurantItemACIdx = -1;
      this.showRestaurantItemAC = this.restaurantItemHints.length > 0;
      if (this.showRestaurantItemAC) {
        const el = this.$refs.restaurantItemWrap;
        if (el) {
          const rect = el.getBoundingClientRect();
          this.restaurantItemACStyle = { top: (rect.bottom + 2) + "px", left: rect.left + "px", width: rect.width + "px" };
        }
      }
    },

    moveRestaurantItemAC(dir) {
      if (!this.showRestaurantItemAC) return;
      this.restaurantItemACIdx = Math.max(-1, Math.min(this.restaurantItemHints.length - 1, this.restaurantItemACIdx + dir));
    },

    applyRestaurantHint(hint) {
      this.showRestaurantItemAC = false;
      const item = newItem();
      item.description = hint.name;
      if (hint.unit && hint.quantity != null) {
        item.quantity = hint.quantity;
        item.unit = hint.unit;
      } else {
        item.quantity = hint.quantity_g || 100;
        item.unit = "g";
      }
      item.resolvedSource = "history";
      if (hint.nutrition_per_100g) {
        const servingG = (hint.unit === "serving" && hint.quantity > 0)
          ? Math.round(hint.quantity_g / hint.quantity)
          : (hint.quantity_g || null);
        item.resolvedProduct = {
          name: hint.name, brand: "", serving_size: "",
          quantity_g: servingG, servings_per_container: null,
          nutriscore_grade: null, nova_group: null, ecoscore_grade: null,
          images: { front: null, ingredients: null, nutrition: null },
          allergens: [], analysis_tags: [], vitamins_tags: [], ingredients: [],
          per100g: { ...EMPTY_PER100G, ...hint.nutrition_per_100g },
        };
      }
      const isDefault = this.items.length === 1 && !this.items[0].description && !this.items[0].resolvedProduct;
      if (isDefault) this.items = [item];
      else this.items.push(item);
      this.restaurantItemQuery = "";
      this.restaurantItemHints = [];
    },

    addRestaurantComponent() {
      const q = this.restaurantItemQuery.trim();
      if (!q) return;
      if (this.restaurantItemACIdx >= 0 && this.restaurantItemHints[this.restaurantItemACIdx]) {
        this.applyRestaurantHint(this.restaurantItemHints[this.restaurantItemACIdx]);
        return;
      }
      const description = `${q} from ${this.selectedRestaurant.name}`;
      const clientId = crypto.randomUUID();
      const item = newItem();
      item.description = description;
      item.loading = true;
      item._clientId = clientId;
      item._prefetching = true;
      const isDefault = this.items.length === 1 && !this.items[0].description && !this.items[0].resolvedProduct;
      if (isDefault) this.items = [item];
      else this.items.push(item);
      const reactiveItem = this.items[this.items.length - 1];
      this.restaurantItemQuery = "";
      this.showRestaurantItemAC = false;
      this.restaurantItemACIdx = -1;
      this._prefetchRestaurantItem(reactiveItem, clientId, description);
    },

    async _prefetchRestaurantItem(item, clientId, description) {
      try {
        const resp = await fetch(apiBase(), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source: "item_prefetch", client_id: clientId, description }),
        });
        if (!resp.ok) {
          item.lookupError = `Nutrition lookup failed (${resp.status}) — will estimate on submit`;
          return;
        }
        const result = await this._pollItemPrefetch(clientId);
        if (result?.components?.length) {
          const comp = result.components[0];
          item.resolvedSource = "restaurant";
          item.resolvedProduct = {
            name: comp.name,
            brand: "", serving_size: "",
            quantity_g: comp.quantity_g || null,
            servings_per_container: null,
            nutriscore_grade: null, nova_group: null, ecoscore_grade: null,
            images: { front: null, ingredients: null, nutrition: null },
            allergens: [], analysis_tags: [], vitamins_tags: [], ingredients: [],
            per100g: { ...EMPTY_PER100G, ...comp.nutrition_per_100g },
          };
          item._prefetchComponents = result.components;
        } else {
          item.lookupError = "Nutrition lookup timed out — will estimate on submit";
        }
      } catch (e) {
        item.lookupError = `Lookup failed: ${e.message}`;
      } finally {
        item.loading = false;
        item._prefetching = false;
      }
    },

    async _pollItemPrefetch(clientId) {
      const url = `${s3Base()}/diet/prefetch/${clientId}.json`;
      for (let i = 0; i < 30; i++) {
        await new Promise(r => setTimeout(r, 3000));
        try {
          const resp = await fetch(url);
          if (resp.ok) return await resp.json();
        } catch {}
      }
      return null;
    },

    _closeRestaurantItemACDelayed() {
      setTimeout(() => { this.showRestaurantItemAC = false; }, 160);
    },

    // ── Save recipe ──
    async saveRecipe() {
      if (!this.saveRecipeName.trim() || !this.saveableItems.length) return;
      this.savingRecipe = true;
      try {
        const itemsToSave = this.saveableItems.map(it => ({
          name: it.resolvedProduct.name,
          quantity_g: this.estimateGrams(it) || it.quantity,
          source: it.resolvedSource || "history",
          barcode: it.barcode || null,
          nutrition_per_100g: it.resolvedProduct.per100g,
        }));
        const client_id = crypto.randomUUID();
        const body = {
          source: "recipe",
          client_id,
          name: this.saveRecipeName.trim(),
          date: this.date,
          time: this.time,
          items: itemsToSave,
        };
        const resp = await fetch(this.endpointUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (resp.ok) {
          this.savedRecipes.push({ id: client_id, name: body.name, saved_at: this.date, items: itemsToSave, _type: "saved" });
          this.saveRecipeDialog = false;
          this.saveRecipeName = "";
          this.snackbar = { show: true, text: `Recipe "${body.name}" saved!`, color: "success" };
        } else {
          this.snackbar = { show: true, text: `Save failed: ${resp.status}`, color: "error" };
        }
      } catch (e) {
        this.snackbar = { show: true, text: `Failed: ${e.message}`, color: "error" };
      } finally {
        this.savingRecipe = false;
      }
    },

    // ── Ingredient autocomplete ──
    onDescriptionInput(i) {
      const item = this.items[i];
      const q = (item.description || "").trim();
      if (q.length < 2) { item.autocomplete = []; item.showAutocomplete = false; return; }
      const words = q.toLowerCase().split(/\s+/);
      item.autocomplete = this.historyComponents
        .filter(c => words.every(w => c.name.toLowerCase().includes(w)))
        .slice(0, 7);
      item.showAutocomplete = item.autocomplete.length > 0;
      item.autocompleteIdx = -1;
      if (item.showAutocomplete) {
        const el = this.acRefs[i];
        if (el) {
          const rect = el.getBoundingClientRect();
          item.acDropStyle = { top: (rect.bottom + 2) + "px", left: rect.left + "px", width: rect.width + "px" };
        }
      }
    },
    applyAutocomplete(item, comp) {
      item.description = comp.name;
      item.barcode = comp.barcode || "";
      if (comp.unit && comp.quantity != null) {
        item.quantity = comp.quantity;
        item.unit = comp.unit;
      } else {
        item.quantity = comp.quantity_g || 1;
        item.unit = "g";
      }
      item.showAutocomplete = false;
      item.autocomplete = [];
      if (comp.nutrition_per_100g) {
        const servingG = (comp.unit === "serving" && comp.quantity > 0)
          ? Math.round(comp.quantity_g / comp.quantity)
          : (comp.quantity_g || null);
        item.resolvedSource = "history";
        item.resolvedProduct = {
          name: comp.name, brand: "", serving_size: "", quantity_g: servingG, servings_per_container: null,
          nutriscore_grade: null, nova_group: null, ecoscore_grade: null,
          images: { front: null, ingredients: null, nutrition: null },
          allergens: [], analysis_tags: [], vitamins_tags: [], ingredients: [],
          per100g: { ...EMPTY_PER100G, ...comp.nutrition_per_100g },
        };
      }
    },
    moveAutocomplete(i, dir) {
      const item = this.items[i];
      if (!item.showAutocomplete) return;
      item.autocompleteIdx = Math.max(-1, Math.min(item.autocomplete.length - 1, item.autocompleteIdx + dir));
    },
    selectAutocomplete(i) {
      const item = this.items[i];
      if (item.autocompleteIdx >= 0 && item.autocomplete[item.autocompleteIdx]) {
        this.applyAutocomplete(item, item.autocomplete[item.autocompleteIdx]);
      }
    },
    closeAutocomplete(i) { if (this.items[i]) this.items[i].showAutocomplete = false; },
    _closeAutocompleteDelayed(i) { setTimeout(() => this.closeAutocomplete(i), 160); },
    clearResolved(item) { item.resolvedProduct = null; item.resolvedSource = null; item.barcode = ""; item.lookupError = null; },

    // ── Display helpers ──
    fmt0(v) { return v != null ? v.toFixed(0) : "—"; },
    fmt1(v) { return v != null ? v.toFixed(1) : "—"; },
    fmt2(v) { return v != null ? v.toFixed(1) : "—"; },
    nutriscoreColor(grade) { return NUTRISCORE_COLORS[grade?.toLowerCase()] || "grey"; },
    novaColor(g) { return NOVA_COLORS[g] || "grey"; },
    novaLabel(g) { return NOVA_LABELS[g] || ""; },
    analysisTagColor(tag) { return ANALYSIS_TAG_COLORS[tag] || "grey"; },
    formatTag(tag) { return tag.replace(/-/g, " ").replace(/\b\w/g, c => c.toUpperCase()); },

    // ── Item management ──
    addItem() { this.items.push(newItem()); },
    availableUnits(item) {
      const base = [...UNITS];
      if (item.resolvedProduct?.quantity_g && !base.includes("serving")) base.unshift("serving");
      return base;
    },
    estimateGrams(item) {
      const { quantity, unit, resolvedProduct } = item;
      if (unit === "g") return quantity;
      if (unit === "oz") return quantity * 28.35;
      if (unit === "tbsp") return quantity * 15;
      if (unit === "tsp") return quantity * 5;
      if (unit === "cup") return quantity * 240;
      if (unit === "fl oz") return quantity * 29.57;
      if (unit === "ml") return quantity;
      if (unit === "serving" && resolvedProduct?.quantity_g) return quantity * resolvedProduct.quantity_g;
      return null;
    },
    itemTotal(item) {
      const grams = this.estimateGrams(item);
      const per100g = item.resolvedProduct?.per100g;
      if (grams === null || !per100g) return null;
      const f = grams / 100;
      return {
        calories: (per100g.calories_kcal || 0) * f,
        protein: (per100g.protein_g || 0) * f,
        fat: (per100g.total_fat_g || 0) * f,
        carbs: (per100g.total_carbohydrate_g || 0) * f,
      };
    },

    // ── Camera barcode scanner ──
    openScanner(item) {
      this.scannerItem = item;
      this.scannerError = null;
      this.scannerOpen = true;
    },
    async _startScanner() {
      const ZXing = window.ZXing;
      if (!ZXing) { this.scannerError = "ZXing library not loaded"; return; }
      const video = this.$refs.scannerVideo;
      if (!video) { this.scannerError = "Camera element not ready"; return; }
      try {
        this._codeReader = new ZXing.BrowserMultiFormatReader();
        await this._codeReader.decodeFromConstraints(
          { video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } } },
          video,
          (result) => {
            if (!result) return;
            const barcode = result.getText();
            this.scannerOpen = false;
            this._onBarcodeDetected(barcode);
          }
        );
      } catch (e) {
        this.scannerError = e.name === "NotAllowedError" ? "Camera permission denied" : (e.message || "Camera error");
      }
    },
    _stopScanner() {
      if (this._codeReader) { this._codeReader.reset(); this._codeReader = null; }
      this.scannerItem = null;
    },
    _onBarcodeDetected(barcode) {
      if (!this.scannerItem) return;
      this.scannerItem.barcode = barcode;
      this.scannerItem.description = barcode;
      this.lookupBarcode(this.scannerItem);
    },
    submitManualBarcode() {
      const barcode = (this.scannerManualBarcode || "").trim();
      if (!barcode) return;
      this.scannerOpen = false;
      this._onBarcodeDetected(barcode);
    },

    // ── OFf barcode lookup ──
    async lookupBarcode(item) {
      if (!item.barcode) return;
      item.loading = true;
      item.lookupError = null;
      item.resolvedProduct = null;
      try {
        const resp = await fetch(`https://world.openfoodfacts.org/api/v0/product/${item.barcode}.json`);
        const data = await resp.json();
        if (data.status === 1) {
          const p = data.product;
          const nm = p.nutriments || {};
          const mg = (v) => v != null ? v * 1000 : null;
          item.resolvedSource = "openfoodfacts";
          item.resolvedProduct = {
            name: p.product_name || p.product_name_en || "Unknown product",
            brand: p.brands || "",
            serving_size: p.serving_size || "",
            quantity_g: p.serving_quantity ? parseFloat(p.serving_quantity) : null,
            servings_per_container: p.servings_per_container ? parseFloat(p.servings_per_container) : null,
            nutriscore_grade: p.nutriscore_grade || null,
            nova_group: p.nova_group ? parseInt(p.nova_group) : null,
            ecoscore_grade: p.ecoscore_grade || null,
            images: {
              front: p.image_front_small_url || p.image_small_url || null,
              ingredients: p.image_ingredients_small_url || null,
              nutrition: p.image_nutrition_small_url || null,
            },
            allergens: (p.allergens || "").split(",").map(a => a.trim().replace(/^en:/, "")).filter(Boolean),
            analysis_tags: (p.ingredients_analysis_tags || []).map(t => t.replace(/^en:/, "")),
            vitamins_tags: (p.vitamins_tags || []).map(v => v.replace(/^en:/, "").replace(/-/g, " ")),
            ingredients: (p.ingredients || []).map(ing => ({
              text: ing.text || "",
              percent: ing.percent_estimate != null ? Math.round(ing.percent_estimate * 10) / 10 : null,
              vegan: ing.vegan || null,
            })),
            per100g: {
              calories_kcal:         nm["energy-kcal_100g"] ?? (nm["energy_100g"] ? nm["energy_100g"] / 4.184 : null),
              protein_g:             nm["proteins_100g"] ?? null,
              total_fat_g:           nm["fat_100g"] ?? null,
              saturated_fat_g:       nm["saturated-fat_100g"] ?? null,
              monounsaturated_fat_g: nm["monounsaturated-fat_100g"] ?? null,
              polyunsaturated_fat_g: nm["polyunsaturated-fat_100g"] ?? null,
              omega3_g:              nm["omega-3-fat_100g"] ?? null,
              trans_fat_g:           nm["trans-fat_100g"] ?? null,
              total_carbohydrate_g:  nm["carbohydrates_100g"] ?? null,
              fiber_g:               nm["fiber_100g"] ?? null,
              sugar_g:               nm["sugars_100g"] ?? null,
              added_sugar_g:         nm["added-sugars_100g"] ?? null,
              starch_g:              nm["starch_100g"] ?? null,
              cholesterol_mg:        mg(nm["cholesterol_100g"]),
              sodium_mg:             mg(nm["sodium_100g"]),
              potassium_mg:          mg(nm["potassium_100g"]),
              calcium_mg:            mg(nm["calcium_100g"]),
              iron_mg:               mg(nm["iron_100g"]),
              magnesium_mg:          mg(nm["magnesium_100g"]),
              zinc_mg:               mg(nm["zinc_100g"]),
              vitamin_a_ug:          nm["vitamin-a_100g"] ?? null,
              vitamin_c_mg:          nm["vitamin-c_100g"] ?? null,
              vitamin_d_ug:          nm["vitamin-d_100g"] ?? null,
              vitamin_b12_ug:        nm["vitamin-b12_100g"] ?? null,
              folate_ug:             nm["vitamin-b9_100g"] ?? null,
            },
          };
          item.description = item.resolvedProduct.name;
          if (item.resolvedProduct.quantity_g) item.unit = "serving";
          // Track OFf lookup usage (fire-and-forget)
          fetch(apiBase(), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source: "usage_event", event_type: "off_lookups", client_id: crypto.randomUUID() }),
          }).catch(() => {});
        } else {
          item.lookupError = `Barcode ${item.barcode} not found in Open Food Facts`;
        }
      } catch (e) {
        item.lookupError = `Lookup failed: ${e.message}`;
      } finally {
        item.loading = false;
      }
    },

    // ── Submit entry ──
    async postEntry() {
      if (!this.endpointUrl) return;
      this.submitting = true;
      try {
        const mappedItems = this.items
          .filter(item => item.resolvedProduct ? item.resolvedProduct.name : item.description)
          .flatMap(item => {
            if (item._prefetchComponents?.length) {
              return item._prefetchComponents.map(comp => ({
                source: "restaurant",
                name: comp.name,
                quantity_g: comp.quantity_g,
                nutrition_per_100g: comp.nutrition_per_100g,
              }));
            }
            const quantity_g = this.estimateGrams(item);
            if (item.resolvedProduct) {
              return [{
                source: item.resolvedSource || "openfoodfacts",
                barcode: item.barcode || null,
                name: item.resolvedProduct.name,
                quantity: item.quantity,
                unit: item.unit,
                quantity_g,
                nutrition_per_100g: item.resolvedProduct.per100g,
              }];
            }
            return [{
              source: "text",
              description: item.description,
              quantity: item.quantity,
              unit: item.unit,
              quantity_g,
            }];
          });
        const body = {
          date: this.date,
          time: this.time,
          client_id: crypto.randomUUID(),
          items: mappedItems,
        };
        const resp = await fetch(this.endpointUrl, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (resp.ok) {
          this.snackbar = { show: true, text: "Entry submitted!", color: "success" };
          this.showPreview = false;
          this.items = [newItem()];
        } else {
          this.snackbar = { show: true, text: `Server error: ${resp.status}`, color: "error" };
        }
      } catch (e) {
        this.snackbar = { show: true, text: `Failed: ${e.message}`, color: "error" };
      } finally {
        this.submitting = false;
      }
    },
  },
};
</script>
