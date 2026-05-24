<template>
  <v-container class="py-6" style="max-width:600px">

    <!-- Header -->
    <div class="d-flex align-center justify-space-between mb-4">
      <div>
        <div class="text-h6 font-weight-bold">Recipes</div>
        <div class="text-caption text-grey">{{ recipes.length }} saved</div>
      </div>
      <div class="d-flex gap-2">
        <v-btn variant="outlined" color="green-darken-2" size="small" @click="addRecipe">
          <v-icon icon="fas fa-plus" size="x-small" class="mr-1" />New
        </v-btn>
        <v-btn
          color="green-darken-2"
          size="small"
          :variant="isDirty ? 'flat' : 'outlined'"
          :disabled="!isDirty"
          :loading="saving"
          @click="saveAll"
        >Save</v-btn>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="green-darken-2" size="48" />
    </div>

    <!-- Empty state -->
    <div v-else-if="!recipes.length" class="text-center py-12 text-grey">
      <v-icon icon="fas fa-bookmark" size="64" class="mb-4 text-grey-lighten-1" />
      <div class="text-body-1">No saved recipes yet</div>
      <div class="text-caption mt-2">Save a recipe from the Add tab, or click New above</div>
    </div>

    <!-- Recipe list -->
    <template v-else>
      <v-card
        v-for="(recipe, i) in recipes"
        :key="recipe.id || i"
        class="mb-3"
        rounded="lg"
        elevation="1"
        style="overflow:visible"
      >
        <v-card-text class="py-3">

          <!-- Collapsed row -->
          <template v-if="expandedIdx !== i">
            <div class="d-flex align-center gap-2">
              <div class="flex-grow-1" style="min-width:0">
                <div class="text-body-1 font-weight-medium" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ recipe.name }}</div>
                <div class="text-caption text-grey">
                  {{ formatDate(recipe.saved_at) }}
                  · {{ recipeKcal(recipe).toFixed(0) }} kcal
                  · {{ (recipe.items || []).length }} ingredient{{ (recipe.items || []).length !== 1 ? 's' : '' }}
                  <a v-if="recipe.source_url" :href="recipe.source_url" target="_blank" class="ml-1 text-green-darken-2" style="text-decoration:none">
                    <v-icon icon="fas fa-link" size="x-small" />
                  </a>
                </div>
              </div>
              <v-btn size="small" variant="tonal" color="green-darken-2" style="min-width:52px" :disabled="!(recipe.items || []).length" @click="useRecipe(recipe)">Use</v-btn>
              <v-btn icon variant="text" size="small" @click="openExpanded(i)">
                <v-icon icon="fas fa-chevron-down" size="x-small" />
              </v-btn>
            </div>
          </template>

          <!-- Expanded editor -->
          <template v-else>

            <!-- Name + collapse -->
            <div class="d-flex align-center gap-2 mb-3">
              <v-text-field
                v-model="recipe.name"
                density="compact"
                variant="outlined"
                hide-details
                label="Recipe name"
                class="flex-grow-1"
                @input="isDirty = true"
              />
              <v-btn icon variant="text" size="small" @click="closeExpanded">
                <v-icon icon="fas fa-chevron-up" size="x-small" />
              </v-btn>
            </div>

            <!-- Source URL -->
            <v-text-field
              v-model="recipe.source_url"
              density="compact"
              variant="outlined"
              hide-details
              label="Source URL"
              placeholder="https://..."
              class="mb-3"
              @input="isDirty = true"
            >
              <template #prepend-inner>
                <v-icon icon="fas fa-link" size="x-small" color="grey" class="mr-1 mt-1" />
              </template>
              <template v-if="recipe.source_url" #append-inner>
                <v-btn icon variant="text" size="x-small" :href="recipe.source_url" target="_blank" title="Open link">
                  <v-icon icon="fas fa-external-link-alt" size="x-small" color="green-darken-2" />
                </v-btn>
              </template>
            </v-text-field>

            <!-- Notes -->
            <v-textarea
              v-model="recipe.notes"
              density="compact"
              variant="outlined"
              hide-details
              label="Notes"
              placeholder="Preparation tips, modifications, etc."
              rows="2"
              auto-grow
              class="mb-3"
              @input="isDirty = true"
            />

            <!-- Ingredient list -->
            <div class="text-caption font-weight-medium text-grey-darken-2 mb-1">
              Ingredients ({{ (recipe.items || []).length }})
            </div>
            <div class="pa-2 bg-grey-lighten-4 rounded mb-2" style="overflow:visible">
              <div v-if="!(recipe.items || []).length" class="text-caption text-grey text-center py-1">
                Search history below to add ingredients
              </div>
              <div
                v-for="(item, j) in recipe.items || []"
                :key="j"
                class="d-flex align-center py-1 gap-1"
                :style="j < (recipe.items.length - 1) ? 'border-bottom:1px solid #e8e8e8' : ''"
              >
                <div class="flex-grow-1" style="min-width:0">
                  <div class="text-caption" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ item.name }}</div>
                  <div v-if="naturalUnit(item.quantity_g)" style="font-size:10px;color:#9e9e9e">≈ {{ naturalUnit(item.quantity_g) }}</div>
                </div>
                <input
                  type="number"
                  min="0"
                  step="1"
                  :value="Math.round(item.quantity_g || 0)"
                  @change="e => updateItemQty(recipe, j, e.target.value)"
                  style="width:48px;border:1px solid #ddd;border-radius:3px;padding:1px 3px;font-size:11px;text-align:right;background:white"
                />
                <span class="text-caption text-grey flex-shrink-0">g</span>
                <span class="text-caption text-grey flex-shrink-0" style="min-width:44px;text-align:right">{{ itemKcal(item).toFixed(0) }} kcal</span>
                <v-btn icon variant="text" size="x-small" color="grey" @click="removeIngredient(recipe, j)">
                  <v-icon icon="fas fa-times" size="x-small" />
                </v-btn>
              </div>
              <!-- Totals row -->
              <div v-if="(recipe.items || []).length" class="d-flex align-center justify-space-between pt-1 mt-1" style="border-top:1px solid #ddd">
                <span class="text-caption font-weight-medium text-green-darken-2">{{ recipeKcal(recipe).toFixed(0) }} kcal</span>
                <span class="text-caption text-grey">
                  P {{ recipeMacro(recipe, 'protein_g').toFixed(1) }}g
                  · F {{ recipeMacro(recipe, 'total_fat_g').toFixed(1) }}g
                  · C {{ recipeMacro(recipe, 'total_carbohydrate_g').toFixed(1) }}g
                </span>
              </div>
            </div>

            <!-- Add ingredient from history -->
            <div style="position:relative;margin-bottom:12px">
              <v-text-field
                v-model="addIngSearch"
                density="compact"
                variant="outlined"
                hide-details
                label="Add ingredient from history"
                placeholder="e.g. peanut butter, strawberries"
                clearable
                @input="onAddIngInput"
                @keydown.down.prevent="moveAddIngAC(1)"
                @keydown.up.prevent="moveAddIngAC(-1)"
                @keydown.enter.prevent="selectAddIngAC(recipe)"
                @keydown.esc="showAddIngAC = false"
                @blur="_closeAddIngACDelayed"
              >
                <template #prepend-inner>
                  <v-icon icon="fas fa-plus" size="x-small" color="green-darken-2" class="mr-1 mt-1" />
                </template>
              </v-text-field>
              <div
                v-if="showAddIngAC && addIngAC.length"
                style="position:fixed;z-index:9999;background:#fff;border:1px solid #e0e0e0;border-radius:4px;box-shadow:0 4px 16px rgba(0,0,0,0.18);max-height:220px;overflow-y:auto;min-width:260px"
                :style="addIngDropStyle"
              >
                <div
                  v-for="(comp, k) in addIngAC"
                  :key="k"
                  class="px-3 py-2"
                  :style="{ background: addIngACIdx === k ? '#f5f5f5' : '#fff', cursor: 'pointer', borderBottom: '1px solid #f5f5f5', minHeight: '44px' }"
                  @mousedown.prevent="addIngredient(recipe, comp)"
                >
                  <div class="text-body-2">{{ comp.name }}</div>
                  <div class="text-caption text-grey">{{ Math.round(comp.quantity_g || 100) }}g · {{ Math.round((comp.nutrition_per_100g?.calories_kcal || 0) * (comp.quantity_g || 100) / 100) }} kcal</div>
                </div>
              </div>
            </div>

            <!-- Footer actions -->
            <div class="d-flex align-center justify-space-between">
              <div>
                <template v-if="pendingDeleteIdx !== i">
                  <v-btn icon variant="text" color="error" size="small" title="Delete recipe" @click="pendingDeleteIdx = i">
                    <v-icon icon="fas fa-trash-alt" size="small" />
                  </v-btn>
                </template>
                <template v-else>
                  <span class="text-caption text-error mr-2">Delete this recipe?</span>
                  <v-btn size="x-small" variant="flat" color="error" class="mr-1" @click="deleteRecipe(i)">Delete</v-btn>
                  <v-btn size="x-small" variant="outlined" @click="pendingDeleteIdx = null">Cancel</v-btn>
                </template>
              </div>
              <v-btn size="small" variant="tonal" color="green-darken-2" :disabled="!(recipe.items || []).length" @click="useRecipe(recipe)">
                <v-icon icon="fas fa-arrow-right" size="x-small" class="mr-1" />Use recipe
              </v-btn>
            </div>

          </template>
        </v-card-text>
      </v-card>
    </template>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000">{{ snackbar.text }}</v-snackbar>
  </v-container>
</template>

<script>
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function s3Base() {
  const v = (typeof window !== "undefined" && window.CTBUS_S3) || "";
  return v === "CTBUS_S3_PLACEHOLDER" ? "" : v;
}
function apiBase() {
  const v = (typeof window !== "undefined" && window.CTBUS_API) || "";
  return v === "CTBUS_API_PLACEHOLDER" ? "/entry" : v;
}

export default {
  name: "RecipesView",
  emits: ["use-recipe"],
  data() {
    return {
      recipes: [],
      loading: true,
      saving: false,
      isDirty: false,
      expandedIdx: null,
      pendingDeleteIdx: null,
      snackbar: { show: false, text: "", color: "success" },
      historyComponents: [],
      addIngSearch: "",
      addIngAC: [],
      showAddIngAC: false,
      addIngACIdx: -1,
      addIngDropStyle: {},
    };
  },
  async created() {
    await this.loadRecipes();
    this._loadHistory();
  },
  methods: {
    async loadRecipes() {
      this.loading = true;
      try {
        const resp = await fetch(`${s3Base()}/diet/recipes.json`);
        if (resp.ok) {
          const data = await resp.json();
          this.recipes = data.map(r => ({ source_url: "", notes: "", ...r }));
        } else {
          this.recipes = [];
        }
      } catch (e) {
        this.recipes = [];
      } finally {
        this.loading = false;
      }
    },

    async _loadHistory() {
      try {
        const idxResp = await fetch(`${s3Base()}/diet/index.json`);
        if (!idxResp.ok) return;
        const dates = await idxResp.json();
        const results = await Promise.all(
          dates.slice(0, 30).map(date =>
            fetch(`${s3Base()}/diet/${date}.json`).then(r => r.ok ? r.json() : null).catch(() => null)
          )
        );
        const seen = new Map();
        for (const dayData of results) {
          if (!dayData) continue;
          for (const entry of dayData.entries || []) {
            for (const comp of entry.components || []) {
              if (comp.name && !seen.has(comp.name)) seen.set(comp.name, comp);
            }
          }
        }
        this.historyComponents = Array.from(seen.values());
      } catch (e) { /* history unavailable */ }
    },

    async saveAll() {
      this.saving = true;
      try {
        const body = { source: "recipe_replace", client_id: crypto.randomUUID(), recipes: this.recipes };
        const resp = await fetch(apiBase(), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
        if (resp.ok) {
          this.isDirty = false;
          this.snackbar = { show: true, text: "Recipes saved!", color: "success" };
        } else {
          this.snackbar = { show: true, text: `Save failed: ${resp.status}`, color: "error" };
        }
      } catch (e) {
        this.snackbar = { show: true, text: `Failed: ${e.message}`, color: "error" };
      } finally {
        this.saving = false;
      }
    },

    addRecipe() {
      const today = new Date().toLocaleDateString("en-CA");
      this.recipes.push({ name: "New Recipe", items: [], saved_at: today, source_url: "", notes: "" });
      this.openExpanded(this.recipes.length - 1);
      this.isDirty = true;
    },

    deleteRecipe(i) {
      this.recipes.splice(i, 1);
      this.expandedIdx = null;
      this.pendingDeleteIdx = null;
      this.isDirty = true;
    },

    useRecipe(recipe) {
      this.$emit("use-recipe", recipe);
    },

    openExpanded(i) {
      this.expandedIdx = i;
      this.pendingDeleteIdx = null;
      this.addIngSearch = "";
      this.addIngAC = [];
      this.showAddIngAC = false;
    },

    closeExpanded() {
      this.expandedIdx = null;
      this.addIngSearch = "";
      this.addIngAC = [];
      this.showAddIngAC = false;
    },

    // ── Ingredient editing ──
    updateItemQty(recipe, j, val) {
      recipe.items[j].quantity_g = Math.max(0, parseFloat(val) || 0);
      this.isDirty = true;
    },
    removeIngredient(recipe, j) {
      recipe.items.splice(j, 1);
      this.isDirty = true;
    },

    // ── Add ingredient from history ──
    onAddIngInput(e) {
      const q = (this.addIngSearch || "").trim().toLowerCase();
      if (q.length < 2) { this.addIngAC = []; this.showAddIngAC = false; return; }
      const words = q.split(/\s+/);
      this.addIngAC = this.historyComponents
        .filter(c => words.every(w => (c.name || "").toLowerCase().includes(w)))
        .slice(0, 6);
      this.showAddIngAC = this.addIngAC.length > 0;
      this.addIngACIdx = -1;
      // Position dropdown using the input element's bounding rect
      if (this.showAddIngAC && e?.target) {
        const el = e.target.closest(".v-text-field") || e.target;
        const rect = el.getBoundingClientRect();
        this.addIngDropStyle = { top: (rect.bottom + 4) + "px", left: rect.left + "px", width: rect.width + "px" };
      }
    },
    moveAddIngAC(dir) {
      if (!this.showAddIngAC) return;
      this.addIngACIdx = Math.max(-1, Math.min(this.addIngAC.length - 1, this.addIngACIdx + dir));
    },
    selectAddIngAC(recipe) {
      if (this.addIngACIdx >= 0 && this.addIngAC[this.addIngACIdx]) this.addIngredient(recipe, this.addIngAC[this.addIngACIdx]);
    },
    _closeAddIngACDelayed() { setTimeout(() => { this.showAddIngAC = false; }, 160); },
    addIngredient(recipe, comp) {
      if (!recipe.items) recipe.items = [];
      recipe.items.push({
        name: comp.name,
        quantity_g: comp.quantity_g || 100,
        source: "history",
        barcode: comp.barcode || null,
        nutrition_per_100g: comp.nutrition_per_100g || null,
      });
      this.addIngSearch = "";
      this.addIngAC = [];
      this.showAddIngAC = false;
      this.isDirty = true;
    },

    // ── Standard unit conversion ──
    naturalUnit(g) {
      if (!g || g <= 0) return null;
      const T = 0.06;
      const checks = [
        { u: "cup",  f: 240,   min: 0.25, max: 6  },
        { u: "tbsp", f: 15,    min: 0.5,  max: 4  },
        { u: "tsp",  f: 5,     min: 0.5,  max: 3  },
        { u: "oz",   f: 28.35, min: 0.5,  max: 16 },
      ];
      for (const { u, f, min, max } of checks) {
        const r = Math.round((g / f) * 4) / 4;
        if (r < min || r > max) continue;
        if (Math.abs(r * f - g) / g >= T) continue;
        const d = this._frac4(r);
        if (d) return `${d} ${u}`;
      }
      return null;
    },
    _frac4(n) {
      if (n <= 0) return null;
      const w = Math.floor(n);
      const q = Math.round((n - w) * 4);
      if (q === 4) return String(w + 1);
      const fs = ["", "¼", "½", "¾"];
      return w === 0 ? (fs[q] || null) : (q ? `${w}${fs[q]}` : String(w));
    },

    // ── Nutrition helpers ──
    recipeKcal(recipe) {
      return (recipe.items || []).reduce((s, item) => s + ((item.nutrition_per_100g?.calories_kcal || 0) * (item.quantity_g || 0) / 100), 0);
    },
    recipeMacro(recipe, field) {
      return (recipe.items || []).reduce((s, item) => s + ((item.nutrition_per_100g?.[field] || 0) * (item.quantity_g || 0) / 100), 0);
    },
    itemKcal(item) {
      return (item.nutrition_per_100g?.calories_kcal || 0) * (item.quantity_g || 0) / 100;
    },
    formatDate(dateStr) {
      if (!dateStr) return "";
      const [y, m, d] = dateStr.split("-").map(Number);
      return `${MONTHS[m - 1]} ${d}, ${y}`;
    },
  },
};
</script>
