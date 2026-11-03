import React, { useEffect, useMemo, useRef } from 'react';
import * as echarts from 'echarts/core';
import { BarChart, PieChart } from 'echarts/charts';
import { GridComponent, TooltipComponent } from 'echarts/components';
import { SVGRenderer } from 'echarts/renderers';

echarts.use([BarChart, PieChart, GridComponent, TooltipComponent, SVGRenderer]);

const COLORS = ['#1b8792', '#60b3b1', '#314c61', '#9bc9b0', '#c6a765', '#89a0b3', '#bd8f84', '#d7cbb5'];

function isDonut(values, unit) {
  const positive = values.filter((value) => typeof value === 'number' && value > 0);
  const total = positive.reduce((sum, value) => sum + value, 0);
  return unit === 'count' && positive.length >= 2 && positive.length <= 8 && Math.max(...positive) / total <= 0.75;
}

function optionsFor(chart, unit) {
  const labels = chart.labels || [];
  const values = chart.values || [];
  const format = (value) => new Intl.NumberFormat(undefined, { maximumFractionDigits: unit === 'count' ? 0 : 2 }).format(Number(value));
  const common = {
    animationDuration: 500,
    color: COLORS,
    textStyle: { fontFamily: 'Segoe UI, Aptos, sans-serif', color: '#536775' },
    tooltip: { trigger: 'item', backgroundColor: '#172e3b', borderWidth: 0, textStyle: { color: '#fff' }, valueFormatter: format },
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
  const horizontal = labels.length > 6 || labels.some((label) => String(label).length > 14);
  if (horizontal) {
    return {
      ...common,
      grid: { top: 8, left: 8, right: 40, bottom: 28, containLabel: true },
      xAxis: { type: 'value', axisLabel: { color: '#80919c', formatter: format }, splitLine: { lineStyle: { color: '#ebf0f2' } } },
      yAxis: { type: 'category', data: [...labels].reverse(), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: '#536775', width: 145, overflow: 'truncate' } },
      series: [{ type: 'bar', data: [...values].reverse(), barMaxWidth: 24, itemStyle: { color: COLORS[0], borderRadius: [0, 4, 4, 0] }, label: { show: true, position: 'right', color: '#364d59', formatter: ({ value }) => format(value) } }],
    };
  }
  return {
    ...common,
    grid: { top: 10, left: 8, right: 18, bottom: 30, containLabel: true },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#dbe4e8' } }, axisTick: { show: false }, axisLabel: { color: '#536775', width: 90, overflow: 'truncate' } },
    yAxis: { type: 'value', axisLabel: { color: '#80919c', formatter: format }, splitLine: { lineStyle: { color: '#ebf0f2' } } },
    series: [{ type: 'bar', data: values, barMaxWidth: 50, itemStyle: { color: ({ dataIndex }) => COLORS[dataIndex % COLORS.length], borderRadius: [4, 4, 0, 0] }, label: { show: true, position: 'top', color: '#364d59', formatter: ({ value }) => format(value) } }],
  };
}

export function KpiChart({ chart, unit, title }) {
  const container = useRef(null);
  const instance = useRef(null);
  const options = useMemo(() => optionsFor(chart, unit), [chart, unit]);

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

  return <div className="dashboard-chart" ref={container} role="img" aria-label={`${title} chart`} />;
}
