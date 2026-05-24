<template>
  <v-container style="max-width:860px" class="py-6">

    <!-- Week navigation -->
    <div class="d-flex align-center justify-center mb-4 gap-2">
      <v-btn icon variant="text" @click="shiftWeek(-1)">
        <v-icon icon="fas fa-chevron-left" />
      </v-btn>
      <v-btn variant="tonal" color="green-darken-2" min-width="220" readonly>
        {{ weekLabel }}
      </v-btn>
      <v-btn icon variant="text" :disabled="!canGoForward" @click="shiftWeek(1)">
        <v-icon icon="fas fa-chevron-right" />
      </v-btn>
    </div>

    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="green-darken-2" size="48" />
    </div>

    <template v-else>
      <!-- Calorie bar chart -->
      <v-card rounded="lg" elevation="1" class="mb-4">
        <v-card-text>
          <div class="d-flex justify-space-between text-caption text-grey mb-2">
            <span>Calories / day</span>
            <span style="opacity:0.6">- - - 2,000 kcal</span>
          </div>
          <!-- 3-zone layout: label(18px) | bar(70px) | axis(22px) = 110px total -->
          <!-- goal line at 2000/2500*70 + 22 = 78px from bottom -->
          <div style="position:relative;height:110px">
            <div style="position:absolute;left:0;right:0;bottom:78px;height:1px;border-top:1px dashed #bbb;pointer-events:none;opacity:0.7"/>
            <div style="display:grid;grid-template-columns:repeat(7,1fr);height:100%">
              <div v-for="day in weekDays" :key="day.date" style="display:flex;flex-direction:column;align-items:center;padding:0 2px">
                <!-- fixed label zone -->
                <div style="height:18px;display:flex;align-items:flex-end;justify-content:center">
                  <span style="font-size:9px;color:#9e9e9e;line-height:1">{{ day.kcal > 0 ? Math.round(day.kcal) : '' }}</span>
                </div>
                <!-- bar zone -->
                <div style="flex:1;display:flex;align-items:flex-end;width:100%">
                  <div style="width:100%"
                    :style="{
                      height: day.kcal > 0 ? Math.max(3, (day.kcal / 2500) * 70) + 'px' : '2px',
                      background: day.kcal > 0 ? (day.kcal > 2200 ? '#FF9800' : '#4CAF50') : '#eee',
                      borderRadius: '3px 3px 0 0',
                    }"/>
                </div>
                <!-- axis zone -->
                <div style="height:22px;width:100%;display:flex;flex-direction:column;align-items:center;padding-top:2px">
                  <div style="width:100%;height:1px;background:#e0e0e0"/>
                  <div style="font-size:10px;color:#9e9e9e;margin-top:3px">{{ day.dayLabel }}</div>
                </div>
              </div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Daily averages + %DV -->
      <v-card rounded="lg" elevation="1" class="mb-4">
        <v-card-title class="text-subtitle-2">
          Daily averages
          <span class="text-caption text-grey font-weight-regular ml-2">{{ daysWithData }}/7 days logged</span>
        </v-card-title>
        <v-card-text class="pt-0">
          <div v-for="stat in dvStats" :key="stat.key" class="mb-3">
            <div class="d-flex justify-space-between text-caption mb-1">
              <span class="text-grey-darken-1">{{ stat.label }}</span>
              <span>
                <span class="font-weight-medium">{{ stat.avgFmt }}</span>
                <span class="text-grey ml-1">{{ stat.unit }}</span>
                <span
                  class="ml-2 font-weight-medium"
                  :style="{ color: dvColor(stat.pctRaw, stat.upper) }"
                >{{ stat.pct }}% DV</span>
              </span>
            </div>
            <div style="height:6px;border-radius:3px;background:#eee;overflow:hidden">
              <div
                :style="{
                  width: Math.min(100, stat.pctRaw) + '%',
                  height: '100%',
                  background: dvColor(stat.pctRaw, stat.upper),
                }"
              />
            </div>
          </div>
        </v-card-text>
      </v-card>

      <!-- Day-by-day table -->
      <v-card rounded="lg" elevation="1">
        <v-table density="compact" class="text-caption">
          <thead>
            <tr class="text-grey">
              <th class="text-left">Day</th>
              <th class="text-right">kcal</th>
              <th class="text-right">P g</th>
              <th class="text-right">F g</th>
              <th class="text-right">C g</th>
              <th class="text-right">Fiber g</th>
              <th class="text-right">Na mg</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="day in weekDays"
              :key="day.date"
              :class="{ 'text-grey-lighten-1': !day.hasData }"
            >
              <td>{{ day.rowLabel }}</td>
              <td class="text-right" :class="{'text-green-darken-2 font-weight-medium': day.hasData}">
                {{ day.hasData ? Math.round(day.kcal) : '—' }}
              </td>
              <td class="text-right">{{ day.hasData ? Math.round(day.protein) : '—' }}</td>
              <td class="text-right">{{ day.hasData ? Math.round(day.fat) : '—' }}</td>
              <td class="text-right">{{ day.hasData ? Math.round(day.carbs) : '—' }}</td>
              <td class="text-right">{{ day.hasData ? Math.round(day.fiber) : '—' }}</td>
              <td class="text-right">{{ day.hasData ? Math.round(day.sodium) : '—' }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card>
    </template>
  </v-container>
</template>

<script>
const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DAYS_SHORT = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

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

function shiftDate(dateStr, days) {
  const d = new Date(dateStr + "T12:00:00");
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-CA");
}

function mondayOf(dateStr) {
  const d = new Date(dateStr + "T12:00:00");
  const dow = d.getDay();
  d.setDate(d.getDate() - (dow === 0 ? 6 : dow - 1));
  return d.toLocaleDateString("en-CA");
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

function fmtNum(v, dec = 0) {
  return v != null ? v.toFixed(dec) : "—";
}

export default {
  name: "WeekView",
  data() {
    return {
      weekStart: mondayOf(localToday()),
      dayDataMap: {},   // date → day JSON or null
      loading: false,
    };
  },
  computed: {
    weekDates() {
      return Array.from({ length: 7 }, (_, i) => shiftDate(this.weekStart, i));
    },
    weekLabel() {
      const start = new Date(this.weekStart + "T12:00:00");
      const end = new Date(this.weekStart + "T12:00:00");
      end.setDate(end.getDate() + 6);
      if (start.getMonth() === end.getMonth()) {
        return `${MONTHS_SHORT[start.getMonth()]} ${start.getDate()}–${end.getDate()}, ${start.getFullYear()}`;
      }
      return `${MONTHS_SHORT[start.getMonth()]} ${start.getDate()} – ${MONTHS_SHORT[end.getMonth()]} ${end.getDate()}`;
    },
    canGoForward() {
      return this.weekStart < mondayOf(localToday());
    },
    weekDays() {
      return this.weekDates.map(date => {
        const data = this.dayDataMap[date];
        const hasData = !!data;
        const d = new Date(date + "T12:00:00");
        return {
          date,
          hasData,
          dayLabel: DAYS_SHORT[d.getDay()],
          rowLabel: `${DAYS_SHORT[d.getDay()]} ${MONTHS_SHORT[d.getMonth()]} ${d.getDate()}`,
          kcal:    sumNutrient(data, "calories_kcal"),
          protein: sumNutrient(data, "protein_g"),
          fat:     sumNutrient(data, "total_fat_g"),
          carbs:   sumNutrient(data, "total_carbohydrate_g"),
          fiber:   sumNutrient(data, "fiber_g"),
          sodium:  sumNutrient(data, "sodium_mg"),
        };
      });
    },
    daysWithData() {
      return this.weekDays.filter(d => d.hasData).length;
    },
    weekAverages() {
      const n = Math.max(1, this.daysWithData);
      const avg = field => this.weekDays.reduce((s, d) => s + (d.hasData ? sumNutrient(this.dayDataMap[d.date], field) : 0), 0) / n;
      return Object.fromEntries(Object.keys(DV).map(k => [k, avg(k)]));
    },
    dvStats() {
      return Object.entries(DV).map(([key, cfg]) => {
        const avg = this.weekAverages[key] ?? 0;
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
    weekStart() { this.loadWeek(); },
  },
  created() {
    this.loadWeek();
  },
  methods: {
    shiftWeek(delta) {
      this.weekStart = shiftDate(this.weekStart, delta * 7);
    },
    async loadWeek() {
      this.loading = true;
      const results = await Promise.all(
        this.weekDates.map(date =>
          fetch(`${s3Base()}/diet/${date}.json`, { cache: "no-cache" })
            .then(r => r.ok ? r.json() : null)
            .catch(() => null)
        )
      );
      const map = {};
      this.weekDates.forEach((date, i) => { map[date] = results[i]; });
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
