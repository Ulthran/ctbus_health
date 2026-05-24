<template>
  <v-container class="py-6" style="max-width: 800px">

    <!-- Date navigation -->
    <div class="d-flex align-center justify-center mb-4 gap-2">
      <v-btn icon variant="text" :disabled="!hasPrev" @click="navigateDate(-1)">
        <v-icon icon="fas fa-chevron-left" />
      </v-btn>
      <v-menu v-model="datePicker" :close-on-content-click="false">
        <template #activator="{ props }">
          <v-btn variant="tonal" color="green-darken-2" v-bind="props" min-width="180">
            <v-icon icon="fas fa-calendar-alt" size="small" class="mr-2" />
            {{ formatDateLabel(currentDate) }}
          </v-btn>
        </template>
        <v-card>
          <v-list density="compact" max-height="320" style="overflow-y:auto">
            <v-list-item
              v-for="d in availableDates"
              :key="d"
              :title="formatDateLabel(d)"
              :active="d === currentDate"
              active-color="green-darken-2"
              @click="currentDate = d; datePicker = false"
            />
          </v-list>
        </v-card>
      </v-menu>
      <v-btn icon variant="text" :disabled="!hasNext" @click="navigateDate(1)">
        <v-icon icon="fas fa-chevron-right" />
      </v-btn>
    </div>

    <!-- Loading / empty states -->
    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="green-darken-2" size="48" />
    </div>
    <div v-else-if="!dayData" class="text-center py-12 text-grey">
      <v-icon icon="fas fa-seedling" size="64" class="mb-4 text-grey-lighten-1" />
      <div>No entries for this day</div>
    </div>

    <template v-else>
      <!-- Day summary card -->
      <v-card rounded="lg" elevation="1" class="mb-4">
        <v-card-text>
          <v-row dense class="text-center mb-2">
            <v-col>
              <div class="text-h5 font-weight-bold text-green-darken-2">{{ totals.kcal.toFixed(0) }}</div>
              <div class="text-caption text-grey">kcal</div>
            </v-col>
            <v-col>
              <div class="text-h6">{{ totals.protein.toFixed(1) }}</div>
              <div class="text-caption text-grey">protein g</div>
            </v-col>
            <v-col>
              <div class="text-h6">{{ totals.fat.toFixed(1) }}</div>
              <div class="text-caption text-grey">fat g</div>
            </v-col>
            <v-col>
              <div class="text-h6">{{ totals.carbs.toFixed(1) }}</div>
              <div class="text-caption text-grey">carbs g</div>
            </v-col>
          </v-row>

          <!-- Macro bar -->
          <div style="height:10px;border-radius:5px;background:#eee;overflow:hidden;margin-bottom:4px">
            <div style="height:100%;display:flex">
              <div :style="{ width: proteinPct + '%', background: '#4CAF50' }" :title="`Protein ${totals.protein.toFixed(1)}g`" />
              <div :style="{ width: fatPct + '%', background: '#FF9800' }" :title="`Fat ${totals.fat.toFixed(1)}g`" />
              <div :style="{ width: carbsPct + '%', background: '#2196F3' }" :title="`Carbs ${totals.carbs.toFixed(1)}g`" />
            </div>
          </div>
          <div class="d-flex text-caption">
            <span class="mr-2"><span style="color:#4CAF50">■</span> protein</span>
            <span class="mr-2"><span style="color:#FF9800">■</span> fat</span>
            <span><span style="color:#2196F3">■</span> carbs</span>
          </div>

          <!-- Micro stats row -->
          <div
            v-if="hasMicro"
            class="d-flex gap-3 mt-3 pa-2 bg-grey-lighten-4 rounded"
            style="overflow-x:auto;flex-wrap:wrap"
          >
            <div v-if="totals.fiber" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-green-darken-2">{{ totals.fiber.toFixed(1) }}g</div>
              <div class="text-caption text-grey">fiber</div>
            </div>
            <div v-if="totals.starch" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-blue-darken-2">{{ totals.starch.toFixed(1) }}g</div>
              <div class="text-caption text-grey">starch</div>
            </div>
            <div v-if="totals.sugar" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium">{{ totals.sugar.toFixed(1) }}g</div>
              <div class="text-caption text-grey">sugar<template v-if="totals.added_sugar"> ({{ totals.added_sugar.toFixed(1) }}g added)</template></div>
            </div>
            <div v-if="totals.sat_fat" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-orange-darken-2">{{ totals.sat_fat.toFixed(1) }}g</div>
              <div class="text-caption text-grey">sat fat</div>
            </div>
            <div v-if="totals.sodium_mg" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-orange-darken-2">{{ totals.sodium_mg.toFixed(0) }}mg</div>
              <div class="text-caption text-grey">sodium</div>
            </div>
            <div v-if="totals.cholesterol_mg" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium">{{ totals.cholesterol_mg.toFixed(0) }}mg</div>
              <div class="text-caption text-grey">chol</div>
            </div>
            <div v-if="totals.potassium_mg" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-green-darken-1">{{ totals.potassium_mg.toFixed(0) }}mg</div>
              <div class="text-caption text-grey">potassium</div>
            </div>
            <div v-if="totals.calcium_mg" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium">{{ totals.calcium_mg.toFixed(0) }}mg</div>
              <div class="text-caption text-grey">calcium</div>
            </div>
            <div v-if="totals.omega3_g" class="text-center" style="min-width:52px">
              <div class="text-body-2 font-weight-medium text-blue-darken-1">{{ totals.omega3_g.toFixed(1) }}g</div>
              <div class="text-caption text-grey">omega-3</div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Entries -->
      <v-card
        v-for="(entry, i) in dayData.entries"
        :key="i"
        rounded="lg"
        elevation="1"
        class="mb-3"
      >
        <v-card-text>
          <!-- Entry header: time + raw description -->
          <div class="d-flex align-start justify-space-between mb-2">
            <div>
              <div class="text-caption text-grey mb-1">{{ formatTime(entry.timestamp) }}</div>
              <div class="text-body-2 text-grey-darken-2 font-italic" style="max-width:480px">
                {{ (entry.raw_texts || []).join('; ') }}
              </div>
            </div>
            <div class="text-right flex-shrink-0 ml-3">
              <div class="text-subtitle-2 text-green-darken-2">{{ entryKcal(entry).toFixed(0) }} kcal</div>
            </div>
          </div>

          <!-- Components table -->
          <v-table density="compact" class="text-caption">
            <thead>
              <tr class="text-grey">
                <th class="text-left" style="padding-left:0">Component</th>
                <th class="text-right">g</th>
                <th class="text-right">kcal</th>
                <th class="text-right">P</th>
                <th class="text-right">F</th>
                <th class="text-right">C</th>
                <th class="text-right"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(comp, j) in entry.components" :key="j">
                <td style="padding-left:0;max-width:200px">
                  <div class="d-flex align-center gap-1">
                    <span>{{ comp.name }}</span>
                  </div>
                </td>
                <td class="text-right text-grey">{{ Number(comp.quantity_g).toFixed(1) }}</td>
                <td class="text-right font-weight-medium">{{ compKcal(comp).toFixed(0) }}</td>
                <td class="text-right text-grey">{{ compNutrient(comp, 'protein_g').toFixed(1) }}</td>
                <td class="text-right text-grey">{{ compNutrient(comp, 'total_fat_g').toFixed(1) }}</td>
                <td class="text-right text-grey">{{ compNutrient(comp, 'total_carbohydrate_g').toFixed(1) }}</td>
                <td class="text-right">
                  <v-chip size="x-small" :color="sourceColor(comp.source)" variant="tonal">
                    {{ sourceLabel(comp.source) }}
                  </v-chip>
                </td>
              </tr>
            </tbody>
          </v-table>

          <!-- Entry micro stats (if any comp has micro data) -->
          <div v-if="entryHasMicro(entry)" class="mt-2 text-caption text-grey d-flex flex-wrap gap-2">
            <span v-if="entryMicro(entry, 'fiber_g')">
              Fiber {{ entryMicro(entry, 'fiber_g').toFixed(1) }}g
            </span>
            <span v-if="entryMicro(entry, 'saturated_fat_g')">
              · Sat {{ entryMicro(entry, 'saturated_fat_g').toFixed(1) }}g
            </span>
            <span v-if="entryMicro(entry, 'sodium_mg')">
              · Na {{ entryMicro(entry, 'sodium_mg').toFixed(0) }}mg
            </span>
            <span v-if="entryMicro(entry, 'sugar_g')">
              · Sugar {{ entryMicro(entry, 'sugar_g').toFixed(1) }}g
            </span>
          </div>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>

<script>
const SOURCE_COLORS = {
  openfoodfacts: "green",
  usda: "orange",
  history: "blue",
  estimated: "grey",
};
const SOURCE_LABELS = {
  openfoodfacts: "OFf",
  usda: "USDA",
  history: "hist",
  estimated: "est",
};
const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

// In prod, window.CTBUS_S3 is the bucket base URL (set by Terraform in index.html).
// Locally, serve.py handles /diet/ routes and CTBUS_S3 stays as the placeholder.
function s3Base() {
  const v = (typeof window !== "undefined" && window.CTBUS_S3) || "";
  return v === "CTBUS_S3_PLACEHOLDER" ? "" : v;
}

function sumNutrient(entries, field) {
  let total = 0, hasAny = false;
  for (const entry of entries) {
    for (const comp of entry.components || []) {
      const n = comp.nutrition_total || {};
      if (n[field] != null) { total += n[field]; hasAny = true; }
    }
  }
  return hasAny ? total : null;
}

export default {
  name: "DashboardView",
  data() {
    return {
      availableDates: [],
      currentDate: null,
      dayData: null,
      loading: false,
      datePicker: false,
    };
  },
  computed: {
    hasPrev() {
      const i = this.availableDates.indexOf(this.currentDate);
      return i < this.availableDates.length - 1;
    },
    hasNext() {
      const i = this.availableDates.indexOf(this.currentDate);
      return i > 0;
    },
    totals() {
      const entries = this.dayData?.entries || [];
      return {
        kcal:           sumNutrient(entries, "calories_kcal") ?? 0,
        protein:        sumNutrient(entries, "protein_g") ?? 0,
        fat:            sumNutrient(entries, "total_fat_g") ?? 0,
        carbs:          sumNutrient(entries, "total_carbohydrate_g") ?? 0,
        fiber:          sumNutrient(entries, "fiber_g"),
        starch:         sumNutrient(entries, "starch_g"),
        sugar:          sumNutrient(entries, "sugar_g"),
        added_sugar:    sumNutrient(entries, "added_sugar_g"),
        sat_fat:        sumNutrient(entries, "saturated_fat_g"),
        sodium_mg:      sumNutrient(entries, "sodium_mg"),
        cholesterol_mg: sumNutrient(entries, "cholesterol_mg"),
        potassium_mg:   sumNutrient(entries, "potassium_mg"),
        calcium_mg:     sumNutrient(entries, "calcium_mg"),
        omega3_g:       sumNutrient(entries, "omega3_g"),
      };
    },
    hasMicro() {
      const t = this.totals;
      return t.fiber || t.starch || t.sugar || t.sat_fat || t.sodium_mg || t.cholesterol_mg || t.potassium_mg || t.calcium_mg || t.omega3_g;
    },
    totalMacroKcal() {
      const t = this.totals;
      return t.protein * 4 + t.fat * 9 + t.carbs * 4;
    },
    proteinPct() {
      if (!this.totalMacroKcal) return 0;
      return Math.min(100, (this.totals.protein * 4 / this.totalMacroKcal) * 100);
    },
    fatPct() {
      if (!this.totalMacroKcal) return 0;
      return Math.min(100, (this.totals.fat * 9 / this.totalMacroKcal) * 100);
    },
    carbsPct() {
      if (!this.totalMacroKcal) return 0;
      return Math.min(100 - this.proteinPct - this.fatPct, (this.totals.carbs * 4 / this.totalMacroKcal) * 100);
    },
  },
  watch: {
    currentDate(date) {
      if (date) this.loadDay(date);
    },
  },
  async created() {
    await this.loadDates();
  },
  methods: {
    async loadDates() {
      try {
        const resp = await fetch(`${s3Base()}/diet/index.json`, { cache: "no-cache" });
        if (!resp.ok) throw new Error(`${resp.status}`);
        this.availableDates = await resp.json();
        if (this.availableDates.length) {
          this.currentDate = this.availableDates[0];
        }
      } catch (e) {
        console.error("Failed to load diet index", e);
      }
    },
    async loadDay(date) {
      this.loading = true;
      this.dayData = null;
      try {
        const resp = await fetch(`${s3Base()}/diet/${date}.json`, { cache: "no-cache" });
        if (resp.ok) this.dayData = await resp.json();
      } catch (e) {
        console.error("Failed to load day", e);
      } finally {
        this.loading = false;
      }
    },
    navigateDate(delta) {
      const i = this.availableDates.indexOf(this.currentDate);
      const next = this.availableDates[i - delta];
      if (next) this.currentDate = next;
    },
    formatDateLabel(dateStr) {
      if (!dateStr) return "";
      const [y, m, d] = dateStr.split("-").map(Number);
      const today = new Date().toLocaleDateString("en-CA");
      const yesterday = new Date(Date.now() - 86400000).toLocaleDateString("en-CA");
      if (dateStr === today) return `Today, ${MONTHS[m - 1]} ${d}`;
      if (dateStr === yesterday) return `Yesterday, ${MONTHS[m - 1]} ${d}`;
      return `${MONTHS[m - 1]} ${d}, ${y}`;
    },
    formatTime(ts) {
      if (!ts) return "";
      const d = new Date(ts);
      const h = d.getHours(), min = d.getMinutes();
      const ampm = h >= 12 ? "PM" : "AM";
      return `${h % 12 || 12}:${String(min).padStart(2, "0")} ${ampm}`;
    },
    sourceColor(src) { return SOURCE_COLORS[src] || "grey"; },
    sourceLabel(src) { return SOURCE_LABELS[src] || src || "?"; },
    entryKcal(entry) {
      return (entry.components || []).reduce((s, c) => s + this.compKcal(c), 0);
    },
    compKcal(comp) {
      return comp.nutrition_total?.calories_kcal
        ?? ((comp.nutrition_per_100g?.calories_kcal ?? 0) * (comp.quantity_g ?? 0) / 100);
    },
    compNutrient(comp, field) {
      if (comp.nutrition_total?.[field] != null) return comp.nutrition_total[field];
      const per100g = comp.nutrition_per_100g?.[field];
      if (per100g != null) return per100g * (comp.quantity_g ?? 0) / 100;
      return 0;
    },
    entryHasMicro(entry) {
      return (entry.components || []).some((c) =>
        c.nutrition_total?.fiber_g != null ||
        c.nutrition_total?.saturated_fat_g != null ||
        c.nutrition_total?.sodium_mg != null
      );
    },
    entryMicro(entry, field) {
      let total = 0, has = false;
      for (const c of entry.components || []) {
        const v = c.nutrition_total?.[field];
        if (v != null) { total += v; has = true; }
      }
      return has ? total : null;
    },
  },
};
</script>
