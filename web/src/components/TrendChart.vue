<template>
  <div ref="el" class="trend" :style="{ height: height + 'px' }"></div>
</template>

<script setup>
// 指标趋势图：X 轴 = 真实检查日期（F-DATA-05），参考范围渲染为浅色区带，
// 曲线走品牌松墨绿、末点金色 —— 与设计系统同源。按需引入控制包体。
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkAreaComponent,
         MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([LineChart, GridComponent, TooltipComponent,
             MarkAreaComponent, MarkLineComponent, CanvasRenderer])

const props = defineProps({
  points: { type: Array, default: () => [] },   // [{date, value, grade}]
  unit: { type: String, default: '' },
  refLow: { type: Number, default: null },
  refHigh: { type: Number, default: null },
  height: { type: Number, default: 220 },
})

const el = ref(null)
let chart = null

function render() {
  if (!el.value) return
  chart = chart || echarts.init(el.value)
  const dates = props.points.map((p) => p.date)
  const values = props.points.map((p) => p.value)
  const markArea = (props.refLow != null && props.refHigh != null)
    ? { silent: true, itemStyle: { color: 'rgba(78,139,109,.08)' },
        data: [[{ yAxis: props.refLow }, { yAxis: props.refHigh }]] }
    : undefined
  const markLine = (props.refHigh != null)
    ? { silent: true, symbol: 'none',
        lineStyle: { color: '#C9A86C', type: 'dashed', width: 1 },
        label: { show: true, position: 'insideEndTop', fontSize: 10,
                 color: '#9A7328', formatter: '参考上限 {c}' },
        data: [{ yAxis: props.refHigh }] }
    : undefined
  chart.setOption({
    grid: { left: 42, right: 16, top: 18, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff', borderColor: '#E2E8E4',
      textStyle: { color: '#33423A', fontSize: 12 },
      formatter: (ps) => {
        const p = ps[0]
        return `${p.axisValue}<br/><b>${p.data}</b> ${props.unit}`
      },
    },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: '#E2E8E4' } },
      axisTick: { show: false },
      axisLabel: { color: '#7C8A82', fontSize: 10,
                   formatter: (v) => v.slice(2) },
    },
    yAxis: {
      type: 'value', scale: true,
      splitLine: { lineStyle: { color: '#EEF2EF' } },
      axisLabel: { color: '#7C8A82', fontSize: 10 },
    },
    series: [{
      type: 'line', data: values, smooth: 0.25,
      symbol: 'circle', symbolSize: 7,
      lineStyle: { color: '#2D5F4B', width: 2.5 },
      itemStyle: {
        color: (p) => p.dataIndex === values.length - 1 ? '#B8912F' : '#2D5F4B',
        borderColor: '#fff', borderWidth: 1.5,
      },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(45,95,75,.16)' },
          { offset: 1, color: 'rgba(45,95,75,0)' },
        ]),
      },
      markArea, markLine,
    }],
    animationDuration: 420,
  })
}

function resize() { chart && chart.resize() }

onMounted(() => { render(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
})
watch(() => [props.points, props.refLow, props.refHigh], render, { deep: true })
</script>

<style scoped>
.trend { width: 100%; }
</style>
