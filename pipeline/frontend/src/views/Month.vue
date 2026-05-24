<template>
  <v-container style="max-width:860px" class="py-6">

    <!-- Month navigation -->
    <div class="d-flex align-center justify-center mb-4 gap-2">
      <v-btn icon variant="text" @click="shiftMonth(-1)">
        <v-icon icon="fas fa-chevron-left" />
      </v-btn>
      <v-btn variant="tonal" color="green-darken-2" min-width="180" readonly>
        {{ monthLabel }}
      </v-btn>
      <v-btn icon variant="text" :disabled="!canGoForward" @click="shiftMonth(1)">
        <v-icon icon="fas fa-chevron-right" />
      </v-btn>
    </div>

    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="green-darken-2" size="48" />
    </div>

    <template v-else>
      <!-- Calorie sparkline for the month -->
      <v-card rounded="lg" elevation="1" class="mb-4">
        <v-card-text>
          <div class="text-caption text-grey mb-2">Calories per day · dashed = 2,000 target · {{ daysWithData }} days logged</div>
          <!-- 2-zone: bar(68px) | axis(22px) = 90px. goal at 2000/2800*68+22 = 70px from bottom -->
          <div style="position:relative;height:90px">
            <div style="position:absolute;left:0;right:0;bottom:70px;height:1px;border-top:1px dashed #bbb;pointer-events:none;opacity:0.7"/>
            <div :style="`display:grid;grid-template-columns:repeat(${monthDays.length},1fr);height:100%`">
              <div v-for="day in monthDays" :key="day.date" style="display:flex;flex-direction:column;align-items:center">
                <!-- bar zone -->
                <div style="flex:1;display:flex;align-items:flex-end;width:100%">
                  <div style="width:100%"
                    :title="`${day.date}: ${day.kcal > 0 ? Math.round(day.kcal) + ' kcal' : 'no data'}`"
                    :style="{
                      height: day.kcal > 0 ? Math.max(2, (day.kcal / 2800) * 68) + 'px' : '2px',
                      background: day.kcal > 0 ? (day.kcal > 2300 ? '#FF9800' : '#4CAF50') : '#eee',
                      borderRadius: '2px 2px 0 0',
                    }"/>
                </div>
                <!-- axis zone -->
                <div style="height:22px;width:100%;display:flex;flex-direction:column;align-items:center;padding-top:2px">
                  <div style="width:100%;height:1px;background:#e0e0e0"/>
                  <div v-if="day.showLabel" style="font-size:8px;color:#9e9e9e;margin-top:2px">{{ day.dayNum }}</div>
                  <div v-else style="height:12px"/>
                </div>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Monthly totals + daily averages with %DV -->
      <v-row class="mb-4">
        <v-col cols="12" md="6">
          <v-card rounded="lg" elevation="1" height="100%">
            <v-card-title class="text-subtitle-2">Monthly totals</v-card-title>
            <v-card-text class="pt-0">
              <v-row dense class="text-center mb-2">
                <v-col>
                  <div class="text-h6 text-green-darken-2">{{ Math.round(monthTotals.kcal) }}</div>
                  <div class="text-caption text-grey">kcal</div>
                </v-col>
                <v-col>
                  <div class="text-h6">{{ Math.round(monthTotals.protein) }}g</div>
                  <div class="text-caption text-grey">protein</div>
                </v-col>
                <v-col>
                  <div class="text-h6">{{ Math.round(monthTotals.fat) }}g</div>
                  <div class="text-caption text-grey">fat</div>
                </v-col>
                <v-col>
                  <div class="text-h6">{{ Math.round(monthTotals.carbs) }}g</div>
                  <div class="text-caption text-grey">carbs</div>
                </v-col>
              </v-row>
              <div class="text-caption text-grey">
                Fiber {{ Math.round(monthTotals.fiber) }}g ·
                Sodium {{ Math.round(monthTotals.sodium / 1000 * 10) / 10 }}g ·
                {{ daysWithData }} days logged
              </div>
            </v-card-text>
          </v-card>
        </v-col>
        <v-col cols="12" md="6">
          <v-card rounded="lg" elevation="1" height="100%">
            <v-card-title class="text-subtitle-2">Macro split (avg/day)</v-card-title>
            <v-card-text class="pt-0">
              <div
                v-for="[label, g, color] in [['Protein', monthAverages.protein_g, '#4CAF50'], ['Fat', monthAverages.total_fat_g, '#FF9800'], ['Carbs', monthAverages.total_carbohydrate_g, '#2196F3']]"
                :key="label"
                class="mb-2"
              >
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span>{{ label }}</span>
                  <span class="font-weight-medium">{{ Math.round(g) }}g</span>
                </div>
                <div style="height:6px;border-radius:3px;background:#eee;overflow:hidden">
                  <div :style="{ width: Math.min(100, (g / (label === 'Protein' ? 50 : label === 'Fat' ? 78 : 275)) * 100) + '%', height: '100%', background: color }" />
                </div>
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- %DV averages -->
      <v-card rounded="lg" elevation="1" class="mb-4">
        <v-card-title class="text-subtitle-2">Daily averages vs %DV</v-card-title>
        <v-card-text class="pt-0">
          <v-row>
            <v-col cols="12" md="6">
              <div v-for="stat in dvStats.slice(0, 6)" :key="stat.key" class="mb-3">
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span class="text-grey-darken-1">{{ stat.label }}</span>
                  <span>
                    <span class="font-weight-medium">{{ stat.avgFmt }}</span>
                    <span class="text-grey ml-1">{{ stat.unit }}</span>
                    <span class="ml-2 font-weight-medium" :style="{ color: dvColor(stat.pctRaw, stat.upper) }">
                      {{ stat.pct }}% DV
                    </span>
                  </span>
                </div>
                <div style="height:6px;border-radius:3px;background:#eee;overflow:hidden">
                  <div :style="{ width: Math.min(100, stat.pctRaw) + '%', height: '100%', background: dvColor(stat.pctRaw, stat.upper) }" />
                </div>
              </div>
            </v-col>
            <v-col cols="12" md="6">
              <div v-for="stat in dvStats.slice(6)" :key="stat.key" class="mb-3">
                <div class="d-flex justify-space-between text-caption mb-1">
                  <span class="text-grey-darken-1">{{ stat.label }}</span>
                  <span>
                    <span class="font-weight-medium">{{ stat.avgFmt }}</span>
                    <span class="text-grey ml-1">{{ stat.unit }}</span>
                    <span class="ml-2 font-weight-medium" :style="{ color: dvColor(stat.pctRaw, stat.upper) }">
                      {{ stat.pct }}% DV
                    </span>
                  </span>
                </div>
                <div style="height:6px;border-radius:3px;background:#eee;overflow:hidden">
                  <div :style="{ width: Math.min(100, stat.pctRaw) + '%', height: '100%', background: dvColor(stat.pctRaw, stat.upper) }" />
                </div>
              </div>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </template>
  </v-container>
</template>

<script>
const MONTHS_LONG = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const DV = {
  calories_kcal:        { label: "Calories",       unit: "kcal", dv: 2000 },
  protein_g:            { label: "Protein",        unit: "g",    dv: 50 },
  total_fat_g:          { label: "Total Fat",      unit: "g",    dv: 78,   upper: true },
  saturated_fat_g:      { label: "Saturated Fat",  unit: "g",    dv: 20,   upper: true },
  cholesterol_mg:       { label: "Cholesterol",    unit: "mg",   dv: 300,  upper: true },
  total_carbohydrate_g: { label: "Carbohydrate",   unit: "g",    dv: 275 },
  fiber_g:              { label: "Fiber",           unit: "g",    dv: 28 },
  sodium_mg:            { label: "Sodium",          unit: "mg",   dv: 2300, upper: true },
  potassium_mg:         { label: "Potassium",       unit: "mg",   dv: 4700 },
  calcium_mg:           { label: "Calcium",         unit: "mg",   dv: 1300 },
  iron_mg:              { label: "Iron",            unit: "mg",   dv: 18 },
};

function s3Base() {
  const v = (typeof window !== "undefined" && window.CTBUS_S3) || "";
  return v === "CTBUS_S3_PLACEHOLDER" ? "" : v;
}

function localToday() {
  return new Date().toLocaleDateString("en-CA");
}

function currentYM() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function datesInMonth(ym) {
  const [y, m] = ym.split("-").map(Number);
  const days = new Date(y, m, 0).getDate();
  return Array.from({ length: days }, (_, i) =>
    `${ym}-${String(i + 1).padStart(2, "0")}`
  );
}

function sumNutrient(dayData, field) {
  let total = 0;
  for (const entry of dayData?.entries || []) {
    for (const comp of entry.components || []) {
      const v = comp.nutrition_total?.[field];
      if (v != null) total += v;
    }
  }
  return total;
}

export default {
  name: "MonthView",
  data() {
    return {
      anchorMonth: currentYM(),
      dayDataMap: {},
      loading: false,
    };
  },
  computed: {
    monthDates() {
      return datesInMonth(this.anchorMonth);
    },
    monthLabel() {
      const [y, m] = this.anchorMonth.split("-").map(Number);
      return `${MONTHS_LONG[m - 1]} ${y}`;
    },
    canGoForward() {
      return this.anchorMonth < currentYM();
    },
    monthDays() {
      return this.monthDates.map((date, i) => {
        const data = this.dayDataMap[date];
        const dayNum = i + 1;
        return {
          date,
          dayNum,
          showLabel: dayNum === 1 || dayNum % 5 === 0,
          hasData: !!data,
          kcal: sumNutrient(data, "calories_kcal"),
        };
      });
    },
    daysWithData() {
      return this.monthDays.filter(d => d.hasData).length;
    },
    monthTotals() {
      const sum = field => this.monthDates.reduce((s, date) => s + sumNutrient(this.dayDataMap[date], field), 0);
      return {
        kcal:    sum("calories_kcal"),
        protein: sum("protein_g"),
        fat:     sum("total_fat_g"),
        carbs:   sum("total_carbohydrate_g"),
        fiber:   sum("fiber_g"),
        sodium:  sum("sodium_mg"),
      };
    },
    monthAverages() {
      const n = Math.max(1, this.daysWithData);
      return Object.fromEntries(
        Object.keys(DV).map(k => [k, this.monthDates.reduce((s, date) => s + sumNutrient(this.dayDataMap[date], k), 0) / n])
      );
    },
    dvStats() {
      return Object.entries(DV).map(([key, cfg]) => {
        const avg = this.monthAverages[key] ?? 0;
        const pctRaw = (avg / cfg.dv) * 100;
        return {
          key,
          label: cfg.label,
          unit: cfg.unit,
          upper: cfg.upper || false,
          avgFmt: avg < 10 ? avg.toFixed(1) : Math.round(avg).toString(),
          pct: Math.round(pctRaw),
          pctRaw,
        };
      });
    },
  },
  watch: {
    anchorMonth() { this.loadMonth(); },
  },
  created() {
    this.loadMonth();
  },
  methods: {
    shiftMonth(delta) {
      const [y, m] = this.anchorMonth.split("-").map(Number);
      const d = new Date(y, m - 1 + delta, 1);
      this.anchorMonth = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
    },
    async loadMonth() {
      this.loading = true;
      const dates = this.monthDates;
      const results = await Promise.all(
        dates.map(date =>
          fetch(`${s3Base()}/diet/${date}.json`, { cache: "no-cache" })
            .then(r => r.ok ? r.json() : null)
            .catch(() => null)
        )
      );
      const map = {};
      dates.forEach((date, i) => { map[date] = results[i]; });
      this.dayDataMap = map;
      this.loading = false;
    },
    dvColor(pct, upper = false) {
      if (upper) {
        if (pct <= 80) return "#4CAF50";
        if (pct <= 100) return "#FF9800";
        return "#F44336";
      }
      if (pct < 50) return "#FF9800";
      if (pct < 100) return "#FFC107";
      return "#4CAF50";
    },
  },
};
</script>
