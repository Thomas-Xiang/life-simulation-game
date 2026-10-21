<script setup>
import { computed, ref, watch } from 'vue';
import { useLife } from './useLife';
import { api, money } from './api';

import StateMap from './components/StateMap.vue';
import TrendChart from './components/TrendChart.vue';

const {
  data,
  session,
  states,
  busy,
  error,
  running,
  autoResume,
  speed,
  comparisons,
  curve,
  life,
  question,
  born,
  refresh,
  step,
  choose,
  erase,
} = useLife();

/* Local interface state */
const selectedState = ref('TX');
const selectedOption = ref('');
const tab = ref('journal');
const chart = ref('wealth');

const deleteConfirm = ref(false);
const message = ref('');
const notice = ref('');
const memorialSubmitted = ref(false);

const wall = ref([]);
const wallLoading = ref(false);
const candleBusy = ref('');
const exporting = ref(false);

/* Display helpers */
function readable(value) {
  if (!value) return 'Not selected';

  return String(value)
    .replaceAll('_', ' ')
    .replaceAll(':', ' · ');
}

function stateName(code) {
  return states.value.find(state => state.code === code)?.name || code || '';
}

function reportError(exception) {
  error.value = exception instanceof Error
    ? exception.message
    : String(exception);
}

const currentState = computed(() =>
  states.value.find(state => state.code === life.value?.state)
);

const previewState = computed(() =>
  states.value.find(state => state.code === selectedState.value)
);

const preview = computed(() =>
  comparisons.value.find(item => item.state === selectedState.value)
);

const localComparison = computed(() =>
  comparisons.value.find(item => item.state === life.value?.home_state)
);

const projection = computed(() => data.value?.projection || {});

const balance = computed(() => data.value?.balance || {});

const journal = computed(() =>
  [...(life.value?.history || [])].reverse()
);

const ledger = computed(() =>
  [...(life.value?.ledger || [])].reverse()
);

const credentials = computed(() =>
  life.value?.credentials || []
);

const partner = computed(() => life.value?.partner || null);

const personalIncome = computed(() =>
  projection.value.personal_income ??
  projection.value.income ??
  0
);

const partnerIncome = computed(() =>
  projection.value.partner_income ?? 0
);

const householdIncome = computed(() =>
  projection.value.income ?? 0
);

const childAges = computed(() =>
  life.value?.dependent_ages || []
);

const totalChildrenChosen = computed(() => {
  const plan = life.value?.family_plan;

  if (plan === 'one') return 1;
  if (plan === 'two') return 2;

  // Compatibility fallback for earlier saves.
  return life.value?.dependents || 0;
});

const statusLabel = computed(() => {
  if (!life.value) return 'A NEW JOURNEY';
  if (life.value.complete) return 'JOURNEY COMPLETE';
  if (question.value) return 'MILESTONE · YOUR NEXT CHAPTER';
  if (running.value) return 'LIFE IN MOTION';

  return 'PAUSED';
});

const pathwayLabel = computed(() => {
  const current = life.value;
  if (!current) return '';

  if (current.program) {
    return (
      `${readable(current.program.kind)} · ` +
      `${current.program.remaining} study years remaining`
    );
  }

  if (current.retired) return 'Retirement chapter';

  return current.major
    ? `${readable(current.major)} · ${current.experience || 0} working years`
    : 'Your story is unfolding';
});

const displayedOptions = computed(() => {
  const current = question.value;
  if (!current) return [];

  if (current.key === 'relocate') {
    return current.options.filter(
      option => option.id === selectedState.value
    );
  }

  return current.options;
});

const canSubmitChoice = computed(() =>
  !busy.value &&
  displayedOptions.value.some(
    option => option.id === selectedOption.value
  )
);

const confirmLabel = computed(() => {
  if (busy.value) return 'Saving…';

  const lastQuestion = (life.value?.queue?.length || 0) === 1;

  if (lastQuestion && autoResume.value) {
    return 'Confirm and continue →';
  }

  return 'Confirm choice →';
});

const metrics = computed(() => {
  if (!life.value) return [];

  return [
    {
      label: 'Cash',
      value: life.value.cash,
      kind: 'cash',
    },
    {
      label: 'Assets',
      value: balance.value.assets,
      kind: 'asset',
    },
    {
      label: 'Total debt',
      value: balance.value.debt,
      kind: 'debt',
    },
    {
      label: 'Net worth',
      value: balance.value.net_worth,
      kind: 'worth',
    },
    {
      label: 'Household gross / year',
      value: householdIncome.value,
      kind: 'income',
    },
    {
      label: 'Living costs / year',
      value: projection.value.living_cost,
      kind: 'cost',
    },
    {
      label: 'Est. surplus / year',
      value: projection.value.surplus,
      kind: 'surplus',
    },
    {
      label: 'Family support / year',
      value: projection.value.support,
      kind: 'support',
    },
  ];
});

/* Reset transient interface state when switching journeys. */
watch(
  () => life.value?.id,
  () => {
    selectedState.value = life.value?.state || 'TX';
    selectedOption.value = '';

    deleteConfirm.value = false;
    message.value = '';
    notice.value = '';
    memorialSubmitted.value = false;

    tab.value = 'journal';
    chart.value = 'wealth';
  }
);

/* Reset the selected answer when the backend changes the question. */
watch(
  () => question.value?.id,
  () => {
    selectedOption.value = '';

    if (question.value?.key === 'relocate') {
      selectedState.value = life.value?.state || 'TX';
    }
  }
);

/* State-map clicks preview a location; only relocation questions commit moves. */
function selectState(code) {
  selectedState.value = code;

  if (question.value?.key === 'relocate') {
    selectedOption.value = code;
  }
}

async function submitChoice() {
  if (!canSubmitChoice.value) return;

  await choose(selectedOption.value);
}

async function startJourney() {
  if (busy.value) return;

  running.value = false;

  // The updated born() archives the previous token and requests a random start.
  await born();
}

function togglePlayback() {
  if (
    busy.value ||
    question.value ||
    !life.value ||
    life.value.complete
  ) {
    return;
  }

  running.value = !running.value;
}

/* Download the saved journey without exposing its access token. */
async function exportLife() {
  if (!session.value || exporting.value) return;

  exporting.value = true;
  let objectUrl;

  try {
    const result = await api(
      `/lives/${session.value.id}/export`,
      { token: session.value.token }
    );

    const blob = new Blob(
      [JSON.stringify(result, null, 2)],
      { type: 'application/json' }
    );

    objectUrl = URL.createObjectURL(blob);

    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = `life-atlas-${session.value.id}.json`;

    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } catch (exception) {
    reportError(exception);
  } finally {
    exporting.value = false;

    if (objectUrl) {
      const urlToRelease = objectUrl;
      setTimeout(() => URL.revokeObjectURL(urlToRelease), 1000);
    }
  }
}

/* Memorials */
async function fetchWall() {
  wallLoading.value = true;

  try {
    wall.value = await api('/memorials');
  } catch (exception) {
    reportError(exception);
  } finally {
    wallLoading.value = false;
  }
}

async function openWall() {
  running.value = false;
  tab.value = 'wall';

  await fetchWall();
}

async function submitMemorial() {
  if (
    busy.value ||
    !session.value ||
    memorialSubmitted.value ||
    life.value?.end_reason !== 'death'
  ) {
    return;
  }

  busy.value = true;
  notice.value = '';

  try {
    await api(
      `/lives/${session.value.id}/memorial`,
      {
        method: 'POST',
        token: session.value.token,
        body: {
          message: message.value.trim(),
        },
      }
    );

    memorialSubmitted.value = true;
    notice.value = 'Submitted for moderation. It is not public yet.';
  } catch (exception) {
    notice.value = exception instanceof Error
      ? exception.message
      : String(exception);
  } finally {
    busy.value = false;
  }
}

async function lightCandle(memorialId) {
  if (candleBusy.value) return;

  candleBusy.value = memorialId;

  try {
    let token = localStorage.getItem('life-atlas-v2-candle');

    if (!token) {
      token = crypto.randomUUID();
      localStorage.setItem('life-atlas-v2-candle', token);
    }

    await api(
      `/memorials/${memorialId}/candle`,
      {
        method: 'POST',
        token,
      }
    );

    await fetchWall();
  } catch (exception) {
    reportError(exception);
  } finally {
    candleBusy.value = '';
  }
}

/* Intentional deletion */
function requestDelete() {
  running.value = false;
  deleteConfirm.value = !deleteConfirm.value;
}

async function deleteJourney() {
  if (busy.value) return;

  await erase();

  if (!life.value) {
    deleteConfirm.value = false;
    notice.value = '';
  }
}
</script>

<template>
  <div class="app-shell">
    <!-- Header -->
    <header>
      <div>
        <b class="brand">
          Life Atlas <span>✦</span>
        </b>

        <small>STATE CHAPTERS · U.S. EDITION</small>
      </div>

      <div v-if="life" class="toolbar">
        <button
          type="button"
          :disabled="busy || wallLoading"
          @click="openWall"
        >
          Memorials
        </button>

        <button
          type="button"
          :disabled="busy"
          @click="refresh"
        >
          Reload
        </button>

        <button
          type="button"
          :disabled="busy || exporting"
          @click="exportLife"
        >
          {{ exporting ? 'Exporting…' : 'Export' }}
        </button>
      </div>
    </header>

    <!-- Model disclosure -->
    <div class="model-banner">
      FICTIONAL ECONOMY · Pay, raises, state costs, partner backgrounds,
      family support and financial outcomes are game scenarios.
      Starting-state weights use 2024 final resident birth counts.
    </div>

    <!-- Errors -->
    <div v-if="error" class="error" role="alert">
      <span>{{ error }}</span>

      <button
        v-if="session"
        type="button"
        :disabled="busy"
        @click="refresh"
      >
        Reload saved journey
      </button>
    </div>

    <!-- Welcome screen -->
    <main v-if="!life" class="welcome">
      <section class="card">
        <span class="eyebrow">A DIFFERENT START</span>

        <h1>
          One life.<br>
          Many places to go.
        </h1>

        <p>
          Your starting state is randomly drawn using 2024 final
          resident birth counts. Family support and your potential
          partner’s background are randomized independently.
        </p>

        <p>
          Choose at meaningful milestones. Education, work, housing,
          relationships and children shape the financial story.
        </p>

        <button
          type="button"
          class="primary"
          :disabled="busy || !states.length"
          @click="startJourney"
        >
          {{ busy ? 'Starting…' : 'Start a random life ↗' }}
        </button>

        <p class="muted">
          No annual career questionnaires. Playback pauses for a
          milestone and resumes after its final choice when enabled.
          Personal finances begin at age 18.
        </p>
      </section>

      <section class="card">
        <h2>Explore the states</h2>

        <StateMap
          :states="states"
          :selected="selectedState"
          :moves="[]"
          @select="selectState"
        />

        <p>
          <b>{{ previewState?.name || 'Select a state to explore' }}</b>
        </p>

        <p v-if="previewState" class="muted">
          Illustrative sector:
          {{ readable(previewState.sector) }}.
          Exploring this map does not choose your starting state.
        </p>

        <p class="muted">
          All 50 states plus DC are included. The map is schematic,
          not a geographic-boundary map.
        </p>
      </section>
    </main>

    <!-- Active or completed journey -->
    <template v-else>
      <!-- Identity and playback -->
      <section class="identity">
        <div>
          <span class="eyebrow">{{ statusLabel }}</span>

          <h1>
            Age {{ life.age }}
            <span>· {{ currentState?.name || life.state }}</span>
          </h1>

          <small>
            {{ readable(life.career) }}
            · {{ readable(life.housing) }}
            · {{ pathwayLabel }}
          </small>
        </div>

        <div class="toolbar">
          <button
            type="button"
            class="primary"
            :disabled="busy || !!question || life.complete"
            @click="togglePlayback"
          >
            {{ running ? 'Pause' : 'Play' }}
          </button>

          <button
            type="button"
            :disabled="busy || running || !!question || life.complete"
            @click="step"
          >
            +1 year
          </button>

          <label>
            Speed

            <select v-model.number="speed">
              <option
                v-for="value in [1, 2, 4, 8]"
                :key="value"
                :value="value"
              >
                {{ value }}×
              </option>
            </select>
          </label>

          <label class="check">
            <input
              v-model="autoResume"
              type="checkbox"
            >
            Resume after choices
          </label>
        </div>
      </section>

      <!-- Compact financial indexes -->
      <section
        class="metrics"
        aria-label="Modeled household financial indexes"
      >
        <article
          v-for="metric in metrics"
          :key="metric.label"
          class="metric"
          :class="metric.kind"
        >
          <small>{{ metric.label }}</small>
          <strong>{{ money(metric.value) }}</strong>
        </article>
      </section>

      <main class="dashboard">
        <!-- Decision / journey card -->
        <section class="card decisions">
          <!-- Current milestone -->
          <template v-if="question">
            <div class="section-head">
              <h2>{{ question.title }}</h2>

              <span class="pill">
                {{ life.queue?.length || 0 }} steps left
              </span>
            </div>

            <p class="muted">
              {{ question.help }}
            </p>

            <form @submit.prevent="submitChoice">
              <fieldset :disabled="busy">
                <legend class="sr-only">
                  {{ question.title }}
                </legend>

                <template v-if="question.key === 'relocate'">
                  <p class="map-hint">
                    Select a state on the map or use the list below.
                    Compare its modeled household surplus against
                    your family-home alternative before confirming.
                  </p>

                  <label class="destination-select">
                    Destination

                    <select
                      :value="selectedState"
                      @change="selectState($event.target.value)"
                    >
                      <option
                        v-for="option in question.options"
                        :key="option.id"
                        :value="option.id"
                      >
                        {{ option.label }}
                      </option>
                    </select>
                  </label>
                </template>

                <div class="option-list">
                  <label
                    v-for="option in displayedOptions"
                    :key="option.id"
                    class="option"
                    :class="{
                      selected: selectedOption === option.id,
                    }"
                  >
                    <input
                      v-model="selectedOption"
                      type="radio"
                      :name="question.id"
                      :value="option.id"
                      required
                    >

                    <span>
                      <b>{{ option.label }}</b>
                      <small>{{ option.impact }}</small>
                    </span>
                  </label>
                </div>
              </fieldset>

              <button
                type="submit"
                class="primary"
                :disabled="!canSubmitChoice"
              >
                {{ confirmLabel }}
              </button>
            </form>
          </template>

          <!-- Completed journey -->
          <template v-else-if="life.complete">
            <span class="eyebrow">YOUR LIFE SUMMARY</span>

            <h2>
              {{
                life.end_reason === 'death'
                  ? 'A life remembered.'
                  : 'Observation complete.'
              }}
            </h2>

            <p>
              {{ life.age }} completed years
              · {{ life.moves?.length || 0 }} moves
              · {{ life.answers?.length || 0 }} choices
            </p>

            <div class="summary-grid">
              <div>
                <small>Final net worth</small>
                <b>{{ money(balance.net_worth) }}</b>
              </div>

              <div>
                <small>Career experience</small>
                <b>{{ life.experience || 0 }} working years</b>
              </div>

              <div>
                <small>Family chapter</small>
                <b>{{ readable(life.relationship) }}</b>
              </div>

              <div>
                <small>Children chosen in this story</small>
                <b>{{ totalChildrenChosen }}</b>
              </div>
            </div>

            <div class="toolbar summary-actions">
              <button
                type="button"
                class="primary"
                :disabled="busy"
                @click="startJourney"
              >
                Start another random life
              </button>

              <button
                type="button"
                :disabled="busy || exporting"
                @click="exportLife"
              >
                Export this journey
              </button>
            </div>

            <p class="muted">
              A new journey gets a new starting-state draw, family
              profile, partner background and mortality draws.
              The previous journey is not deleted.
            </p>

            <p class="muted">
              Reaching the mortality-table boundary ends observation.
              It is not recorded as a sampled death.
            </p>

            <template v-if="life.end_reason === 'death'">
              <label>
                Optional memorial message

                <textarea
                  v-model="message"
                  maxlength="500"
                  rows="2"
                  :disabled="busy || memorialSubmitted"
                  placeholder="A short reflection on this fictional journey."
                />
              </label>

              <button
                type="button"
                :disabled="busy || memorialSubmitted"
                @click="submitMemorial"
              >
                {{
                  memorialSubmitted
                    ? 'Submitted for review'
                    : 'Submit memorial for review'
                }}
              </button>

              <p v-if="notice" role="status" class="muted">
                {{ notice }}
              </p>
            </template>
          </template>

          <!-- No decision needed -->
          <template v-else>
            <span class="eyebrow">
              NO DECISION NEEDED THIS YEAR
            </span>

            <h2>
              {{
                life.program
                  ? 'Learning takes time.'
                  : life.retired
                    ? 'A different pace of life.'
                    : 'Let this chapter unfold.'
              }}
            </h2>

            <p v-if="life.program">
              Your {{ readable(life.program.kind) }} pathway progresses
              automatically. You will choose your next direction when
              the modeled training is complete.
            </p>

            <p v-else-if="life.retired">
              Your retirement income, household expenses and debt
              balances continue updating each year.
            </p>

            <p v-else>
              Your earnings grow with completed working years.
              Household income, expenses, support and debt update
              automatically without reselecting your career.
            </p>

            <p class="muted">
              Milestones include education completion, housing at
              25 and 40, relationships at 28, children at 30, and
              retirement at 65. Deferred relationship or children
              decisions return only once.
            </p>

            <TrendChart
              :ledger="life.ledger"
              :curve="curve"
              :mode="chart"
            />

            <div class="toolbar">
              <button
                type="button"
                :aria-pressed="chart === 'wealth'"
                @click="chart = 'wealth'"
              >
                Net worth
              </button>

              <button
                type="button"
                :aria-pressed="chart === 'survival'"
                @click="chart = 'survival'"
              >
                Survival
              </button>
            </div>
          </template>

          <!-- Family support summary -->
          <div v-if="life.family" class="family-strip">
            <b>
              Starting-family support:
              {{ readable(life.family.level) }}
            </b>

            <small>
              Annual gift {{ money(life.family.annual_gift) }}
              + study help {{ money(life.family.tuition_gift) }}
              before age {{ life.family.until_age }}.
              Family housing
              {{
                life.family.housing
                  ? `available in ${stateName(life.home_state)}`
                  : 'unavailable'
              }}.
              This is a fictional randomized profile.
            </small>
          </div>
        </section>

        <!-- State map and relocation comparison -->
        <section class="card geography">
          <div class="section-head">
            <h2>Where could this life go?</h2>
            <span class="pill">50 states + DC</span>
          </div>

          <StateMap
            :states="states"
            :current="life.state"
            :home="life.home_state"
            :selected="selectedState"
            :moves="life.moves"
            @select="selectState"
          />

          <div v-if="preview" class="comparison">
            <div>
              <b>
                {{ previewState?.name || selectedState }}
              </b>

              <small>
                Illustrative {{ readable(previewState?.sector) }}
                scenario · {{ readable(preview.housing) }}
              </small>

              <dl>
                <dt>Household gross</dt>
                <dd>{{ money(preview.income) }}/yr</dd>

                <dt>Your gross</dt>
                <dd>
                  {{
                    money(
                      preview.personal_income ?? preview.income
                    )
                  }}/yr
                </dd>

                <dt>Partner gross</dt>
                <dd>{{ money(preview.partner_income) }}/yr</dd>

                <dt>Living costs</dt>
                <dd>{{ money(preview.living_cost) }}/yr</dd>

                <dt>Est. surplus</dt>
                <dd :class="{ negative: preview.surplus < 0 }">
                  {{ money(preview.surplus) }}/yr
                </dd>

                <dt>Move cost</dt>
                <dd>{{ money(preview.moving_cost) }}</dd>
              </dl>
            </div>

            <div v-if="localComparison">
              <b>
                Home-state alternative · {{ life.home_state }}
              </b>

              <small>
                {{
                  localComparison.housing === 'parents'
                    ? 'Family housing available'
                    : 'Shared rent; no family housing'
                }}
              </small>

              <dl>
                <dt>Household gross</dt>
                <dd>
                  {{ money(localComparison.income) }}/yr
                </dd>

                <dt>Your gross</dt>
                <dd>
                  {{
                    money(
                      localComparison.personal_income ??
                      localComparison.income
                    )
                  }}/yr
                </dd>

                <dt>Partner gross</dt>
                <dd>
                  {{ money(localComparison.partner_income) }}/yr
                </dd>

                <dt>Living costs</dt>
                <dd>
                  {{ money(localComparison.living_cost) }}/yr
                </dd>

                <dt>Est. surplus</dt>
                <dd
                  :class="{
                    negative: localComparison.surplus < 0,
                  }"
                >
                  {{ money(localComparison.surplus) }}/yr
                </dd>

                <dt>Move cost</dt>
                <dd>{{ money(localComparison.moving_cost) }}</dd>
              </dl>
            </div>
          </div>

          <p class="muted tiny">
            Previews assume shared rent, or family housing in your
            home state when available. They include the modeled
            partner income and extra household costs when married.
            Debt-service estimates are approximate. One-off home-sale
            costs are excluded from this comparison.
          </p>

          <p class="muted tiny">
            Clicking the map previews a state. It does not move your
            household unless you confirm a relocation decision.
          </p>
        </section>

        <!-- Tabbed records -->
        <section class="card records">
          <nav class="tabs" aria-label="Journey records">
            <button
              type="button"
              :class="{ active: tab === 'journal' }"
              @click="tab = 'journal'"
            >
              Journal
            </button>

            <button
              type="button"
              :class="{ active: tab === 'ledger' }"
              @click="tab = 'ledger'"
            >
              Money ledger
            </button>

            <button
              type="button"
              :class="{ active: tab === 'path' }"
              @click="tab = 'path'"
            >
              Life indexes
            </button>

            <button
              type="button"
              :class="{ active: tab === 'wall' }"
              :disabled="wallLoading"
              @click="openWall"
            >
              Memorials
            </button>

            <button
              type="button"
              :class="{ active: tab === 'settings' }"
              @click="tab = 'settings'"
            >
              Data
            </button>
          </nav>

          <!-- Journal -->
          <div
            v-if="tab === 'journal'"
            class="record-body"
          >
            <p v-if="!journal.length" class="muted">
              Your story will appear here.
            </p>

            <article
              v-for="(entry, index) in journal"
              :key="`${entry.age}-${index}`"
              class="journal-entry"
            >
              <span class="pill">{{ entry.age }}</span>

              <div>
                <b>{{ entry.title }}</b>
                <p>{{ entry.text }}</p>
              </div>
            </article>
          </div>

          <!-- Financial ledger -->
          <div
            v-else-if="tab === 'ledger'"
            class="record-body"
          >
            <p class="muted">
              Completed annual intervals, in fictional USD.
              Negative cash flow may be financed by new debt.
              Household gross includes partner earnings when applicable.
            </p>

            <p v-if="!ledger.length" class="muted">
              Financial records begin with the first completed
              interval after age 18.
            </p>

            <table v-else>
              <thead>
                <tr>
                  <th>Age</th>
                  <th>Your gross</th>
                  <th>Partner gross</th>
                  <th>Household gross</th>
                  <th>Tax</th>
                  <th>Support</th>
                  <th>Living</th>
                  <th>Tuition</th>
                  <th>Debt paid</th>
                  <th>Cash flow</th>
                  <th>Net worth</th>
                </tr>
              </thead>

              <tbody>
                <tr
                  v-for="row in ledger"
                  :key="row.age"
                >
                  <td>{{ row.age }}–{{ row.age + 1 }}</td>

                  <td>
                    {{ money(row.personal_income ?? row.income) }}
                  </td>

                  <td>{{ money(row.partner_income) }}</td>
                  <td>{{ money(row.income) }}</td>
                  <td>{{ money(row.tax) }}</td>
                  <td>{{ money(row.support) }}</td>
                  <td>{{ money(row.living) }}</td>
                  <td>{{ money(row.tuition) }}</td>
                  <td>{{ money(row.debt_paid) }}</td>

                  <td :class="{ negative: row.cashflow < 0 }">
                    {{ money(row.cashflow) }}
                  </td>

                  <td :class="{ negative: row.net_worth < 0 }">
                    {{ money(row.net_worth) }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Life indexes -->
          <div
            v-else-if="tab === 'path'"
            class="record-body index-grid"
          >
            <article>
              <b>Education and credentials</b>

              <p v-if="credentials.length">
                {{ credentials.map(readable).join(', ') }}
              </p>

              <p v-else>No completed credentials yet.</p>

              <b>Current program</b>

              <p>
                {{
                  life.program
                    ? `${readable(life.program.kind)}:
                       ${life.program.remaining} years remaining`
                    : 'Not currently studying'
                }}
              </p>

              <b>Career</b>
              <p>{{ readable(life.career) }}</p>

              <b>Your experience</b>
              <p>{{ life.experience || 0 }} completed working years</p>

              <b>Your modeled gross income</b>
              <p>{{ money(personalIncome) }}/year</p>
            </article>

            <article>
              <b>Relationship chapter</b>
              <p>{{ readable(life.relationship) }}</p>

              <template v-if="partner">
                <b>Partner background</b>

                <p>
                  {{ readable(partner.level) }} income background
                  · {{ partner.education }}
                </p>

                <b>Partner modeled gross income</b>
                <p>{{ money(partnerIncome) }}/year</p>

                <b>Partner working years since joining household</b>
                <p>{{ partner.experience || 0 }}</p>
              </template>

              <p v-else>No shared partner finances.</p>

              <b>Children chosen in this story</b>
              <p>{{ totalChildrenChosen }}</p>

              <b>Dependents currently receiving support</b>

              <p>
                {{ life.dependents || 0 }}

                <span v-if="childAges.length">
                  · ages {{ childAges.join(', ') }}
                </span>
              </p>

              <small>
                Modeled dependent costs stop at age 18.
                This does not erase the family story.
              </small>
            </article>

            <article>
              <b>Housing</b>
              <p>{{ readable(life.housing) }}</p>

              <b>Home value / mortgage</b>

              <p>
                {{ money(life.home_value) }}
                / {{ money(life.mortgage) }}
              </p>

              <b>Student debt / other debt</b>

              <p>
                {{ money(life.student_debt) }}
                / {{ money(life.other_debt) }}
              </p>

              <b>Household modeled gross</b>
              <p>{{ money(householdIncome) }}/year</p>

              <b>Game indexes</b>

              <p
                v-for="(value, key) in life.scores"
                :key="key"
              >
                {{ readable(key) }}: {{ value }} / 100
              </p>

              <small>
                Game-design values, not measured health or human worth.
                Wellbeing choices do not alter mortality.
              </small>
            </article>
          </div>

          <!-- Memorial wall -->
          <div
            v-else-if="tab === 'wall'"
            class="record-body"
          >
            <p v-if="wallLoading" role="status">
              Loading memorials…
            </p>

            <p v-else-if="!wall.length" class="muted">
              No approved memorials yet.
            </p>

            <article
              v-for="memorial in wall"
              :key="memorial.id"
              class="journal-entry"
            >
              <div>
                <b>
                  {{ stateName(memorial.state) }}
                  · age {{ memorial.age }}
                </b>

                <p>
                  {{ memorial.message || 'A life remembered.' }}
                </p>

                <button
                  type="button"
                  :disabled="!!candleBusy"
                  @click="lightCandle(memorial.id)"
                >
                  {{
                    candleBusy === memorial.id
                      ? 'Saving…'
                      : `Light a candle · ${memorial.candles}`
                  }}
                </button>
              </div>
            </article>
          </div>

          <!-- Data controls -->
          <div
            v-else
            class="record-body"
          >
            <p>
              Journeys are saved in SQLite. A secret token in this
              browser controls access. There is no account recovery.
              Exporting a journey does not include its access token.
            </p>

            <p>
              Starting another journey does not delete this one.
              The updated start function archives its access credentials
              in this browser, but this interface does not include
              an archive browser.
            </p>

            <div class="toolbar">
              <button
                type="button"
                :disabled="busy || exporting"
                @click="exportLife"
              >
                Export this journey
              </button>

              <button
                type="button"
                :disabled="busy"
                @click="requestDelete"
              >
                {{
                  deleteConfirm
                    ? 'Cancel deletion'
                    : 'Delete this journey'
                }}
              </button>
            </div>

            <div
              v-if="deleteConfirm"
              class="delete-warning"
            >
              <p>
                Permanent deletion also removes this journey’s
                memorial. Export first if you need a record.
              </p>

              <button
                type="button"
                :disabled="busy"
                @click="deleteJourney"
              >
                Permanently delete this journey
              </button>
            </div>
          </div>
        </section>
      </main>
    </template>

    <footer>
      Life Atlas · Fictional financial scenarios · National mortality
      proxy · Compact desktop dashboard; smaller screens scroll.
      No financial, medical, tax or relocation advice.
    </footer>
  </div>
</template>

<style scoped>
.destination-select {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.destination-select select {
  flex: 1;
  min-width: 0;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 10px 0;
}

.summary-grid > div {
  padding: 9px;
  border-radius: 8px;
  background: #f5f3fa;
}

.summary-grid small,
.summary-grid b {
  display: block;
}

.summary-grid b {
  margin-top: 3px;
  font-size: 13px;
}

.summary-actions {
  margin-top: 10px;
}

.delete-warning {
  margin-top: 12px;
  padding: 10px;
  border: 1px solid #dfaaa1;
  border-radius: 8px;
  background: #fff0ec;
}

.error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

@media (max-width: 480px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .error {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>