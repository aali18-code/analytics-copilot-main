import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { CanvasRenderer, SVGRenderer } from 'echarts/renderers';

echarts.use([BarChart, PieChart, GridComponent, TooltipComponent, SVGRenderer, CanvasRenderer]);

const COLORS = ['#1b8792', '#60b3b1', '#314c61', '#9bc9b0', '#c6a765', '#89a0b3', '#bd8f84', '#d7cbb5'];
const COMPARE_COLORS = ['#1b8792', '#c77559', '#7059a3', '#449b78', '#b89536', '#3978b7', '#b35c91', '#697f8d', '#9b6c40', '#5d9d99', '#a95f60', '#6f83b9', '#8c9257', '#ba7c9d'];
const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);

function isDonut(values, unit) {
  const positive = values.filter((value) => typeof value === 'number' && value > 0);
  const total = positive.reduce((sum, value) => sum + value, 0);
  return unit === 'count' && positive.length >= 2 && positive.length <= 8 && Math.max(...positive) / total <= 0.75;
}

function optionsFor(chart, unit, generated = false) {
  const labels = chart.labels || [];
  const values = chart.values || [];
  const format = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: unit === 'count' ? 0 : 2 }).format(Number(value));
  const compact = (value) => new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 }).format(Number(value));
  const common = {
    animationDuration: 500,
    color: COLORS,
    textStyle: { fontFamily: 'Segoe UI, Aptos, sans-serif', color: '#536775' },
    tooltip: { trigger: 'item', backgroundColor: '#172e3b', borderWidth: 0, textStyle: { color: '#fff' }, valueFormatter: format,
      ...(chart.multicolor ? { formatter: (item) => {
        const detail = chart.details?.[item.name];
        if (!detail) return escapeHtml(item.name);
        const average = detail.average_hours === null ? 'n/a' : `${format(detail.average_hours)} hrs`;
        return `${escapeHtml(item.name)}<br/>Average: ${average}<br/>Entries: ${format(detail.count)}<br/>Total: ${format(detail.sum_hours)} hrs`;
      } } : {}) },
  };
  if (isDonut(values, unit)) {
    return {
      ...common,
      series: [{
        type: 'pie', radius: ['57%', '79%'], center: ['50%', '49%'],
        itemStyle: { borderColor: '#fff', borderWidth: 3, borderRadius: 5 },
        label: { show: true, formatter: '{b}\n{d}%', color: '#506573', fontSize: 11 },
        labelLine: { lineStyle: { color: '#b4c4cc' } },
        data: labels.map((name, index) => ({ name, value: values[index] })),
      }],
    };
  }
  const pairedMonth = Boolean(chart.parent_kpi_key);
  const horizontal = !pairedMonth && (labels.length > 6 || labels.some((label) => String(label).length > 14));
  if (horizontal) {
    return {
      ...common,
      grid: { top: 8, left: 8, right: generated ? 75 : 40, bottom: generated ? 36 : 28, containLabel: true },
      xAxis: { type: 'value', splitNumber: generated ? 3 : undefined,
        axisLabel: { color: '#80919c', formatter: generated ? compact : format, hideOverlap: generated },
        splitLine: { lineStyle: { color: '#ebf0f2' } } },
      yAxis: { type: 'category', data: [...labels].reverse(), axisLine: { show: false }, axisTick: { show: false },
        axisLabel: { color: '#536775', width: chart.multicolor ? 180 : generated ? 175 : 145, overflow: 'truncate', interval: 0 } },
      series: [{ type: 'bar', data: [...values].reverse().map((value, index) => chart.multicolor && value !== null
        ? { name: labels[values.length - 1 - index], value, itemStyle: { color: COMPARE_COLORS[(values.length - 1 - index) % COMPARE_COLORS.length] } } : value), barMaxWidth: 24,
        itemStyle: { ...(!chart.multicolor ? { color: COLORS[0] } : {}), borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: '#364d59', fontSize: generated ? 11 : 12,
          formatter: ({ dataIndex, value }) => values[values.length - 1 - dataIndex] == null ? '' : format(value) } }],
    };
  }
  return {
    ...common,
    grid: { top: pairedMonth ? 24 : 10, left: 8, right: 18, bottom: pairedMonth ? 155 : 30, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#dbe4e8' } }, axisTick: { show: false },
      axisLabel: { color: '#536775', width: pairedMonth ? 130 : 90, overflow: 'truncate',
        rotate: pairedMonth ? 65 : 0, interval: 0, fontSize: pairedMonth ? 10 : 12 } },
    yAxis: { type: 'value', name: pairedMonth ? 'Hours' : undefined, axisLabel: { color: '#80919c', formatter: format }, splitLine: { lineStyle: { color: '#ebf0f2' } } },
    series: [{ type: 'bar', data: values, barMaxWidth: pairedMonth ? 28 : 50,
      itemStyle: { color: ({ dataIndex }) => (chart.multicolor ? COMPARE_COLORS : COLORS)[dataIndex % (chart.multicolor ? COMPARE_COLORS : COLORS).length], borderRadius: [4, 4, 0, 0] },
      label: { show: true, position: 'top', color: '#364d59', formatter: ({ dataIndex, value }) => values[dataIndex] == null ? '' : format(value) } }],
  };
}

export function renderChartPng(chart, unit) {
  const width = chart.multicolor ? 1100 : 700;
  const height = chart.multicolor ? Math.max(560, 80 + (chart.labels || []).length * 35) : 350;
  const container = document.createElement('div');
  Object.assign(container.style, {
    position: 'fixed', left: '-10000px', top: '0', width: `${width}px`, height: `${height}px`, pointerEvents: 'none', opacity: '0',
  });
  document.body.appendChild(container);
  let visual;
  try {
    visual = echarts.init(container, null, { renderer: 'canvas', width, height });
    const options = optionsFor(chart, unit);
    const axis = (value) => value ? { ...value, axisLabel: { ...value.axisLabel, fontSize: 15 } } : value;
    visual.setOption({
      ...options,
      animation: false,
      textStyle: { ...options.textStyle, fontSize: 15 },
      xAxis: axis(options.xAxis),
      yAxis: axis(options.yAxis),
      series: options.series.map((item) => ({ ...item, label: { ...item.label, fontSize: 15 } })),
    }, true);
    const png = visual.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#ffffff' });
    if (!png.startsWith('data:image/png;base64,')) throw new Error('The chart could not be captured for PowerPoint.');
    return png;
  } finally {
    visual?.dispose();
    container.remove();
  }
}

export function KpiChart({ chart, unit, title, generated = false }) {
  const container = useRef(null);
  const instance = useRef(null);
  const options = useMemo(() => optionsFor(chart, unit, generated), [chart, unit, generated]);
  const chartHeight = chart.multicolor ? Math.max(480, 70 + (chart.labels || []).length * 32)
    : generated && !isDonut(chart.values || [], unit)
      ? Math.max(270, Math.min(460, 70 + (chart.labels || []).length * 30)) : undefined;

  useEffect(() => {
    const target = container.current;
    if (!target) return undefined;
    const visual = echarts.init(target, null, { renderer: 'svg' });
    instance.current = visual;
    const resize = new ResizeObserver(() => visual.resize());
    resize.observe(target);
    return () => { resize.disconnect(); visual.dispose(); instance.current = null; };
  }, []);

  useEffect(() => { instance.current?.setOption(options, true); }, [options]);

  return <div className="dashboard-chart" ref={container} style={chartHeight ? { height: chartHeight } : undefined} role="img" aria-label={`${title} chart`} />;
}
