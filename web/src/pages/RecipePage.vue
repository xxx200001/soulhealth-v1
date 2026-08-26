<template>
  <div class="page stack" v-if="rc">
    <section class="card fade-in">
      <div class="row-between">
        <h2 style="font-size:20px">{{ rc.name }}</h2>
        <span class="badge badge-gold">{{ rc.serving }}</span>
      </div>
      <p class="reason">{{ rc.reason }}</p>
      <div class="row wrap" style="margin-top: var(--sp-2)">
        <span class="badge badge-quiet">建议频率：{{ rc.frequency }}</span>
        <span class="badge badge-ok">{{ rc.cooking_method }}</span>
      </div>
    </section>

    <!-- 配料克数（F-DIET-04 / AC-12） -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>配料（含克数）</div>
      <div class="table-wrap" style="margin-top: var(--sp-2)">
        <table class="table">
          <tbody>
            <tr v-for="ing in rc.ingredients" :key="ing.name">
              <td><b>{{ ing.name }}</b>
                <span v-if="ing.note" class="tiny">（{{ ing.note }}）</span></td>
              <td class="num" style="text-align:right">{{ ing.grams }} g</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- 步骤 -->
    <section class="card fade-in">
      <div class="card-title"><span class="dot"></span>做法步骤</div>
      <ol class="steps">
        <li v-for="(s, i) in rc.steps" :key="i">{{ s }}</li>
      </ol>
    </section>

    <!-- 不推荐做法 -->
    <section v-if="rc.avoid_methods?.length" class="card fade-in avoidc">
      <div class="card-title" style="color: var(--danger)">
        <span class="dot" style="background: var(--danger)"></span>不推荐的做法
      </div>
      <ul class="av">
        <li v-for="(a, i) in rc.avoid_methods" :key="i">{{ a }}</li>
      </ul>
      <p class="tiny">同一食材，做法不同对健康目标的影响完全不同</p>
    </section>
  </div>
  <div v-else class="page"><div class="empty"><span class="spin"></span></div></div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../api'

const route = useRoute()
const rc = ref(null)

onMounted(async () => {
  try { rc.value = await api.recipe(route.params.rcid) }
  catch (e) { alert(e.message) }
})
</script>

<style scoped>
.reason { margin: var(--sp-2) 0 0; font-size: 13.5px; color: var(--ink-500);
  line-height: 1.7; }
.steps { margin: var(--sp-2) 0 0; padding-left: 22px; }
.steps li { margin: 8px 0; font-size: 14px; line-height: 1.75;
  color: var(--ink-700); }
.steps li::marker { color: var(--gold-600); font-weight: 900;
  font-family: var(--font-serif); }
.avoidc { border-color: #F0CFCA; }
.av { margin: var(--sp-2) 0; padding-left: 18px; font-size: 13.5px;
  color: var(--danger); }
.av li { margin: 4px 0; }
</style>
