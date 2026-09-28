import { filterByRange } from "../charts/history.js";
import { renderExternalChart } from "../charts/external.js";
import { formatDate, formatUnitValue } from "../format.js";
import { openIndicatorDetails } from "../indicator_details.js";
import { DEFAULT_RANGES } from "../config.js";
import { setRangeControlState } from "../ranges.js";
import { renderPaginatedRows } from "../table.js";

const NOTES = {
  policy: "A Taylor dos EUA é uma referência canônica com r*=2%, meta PCE de 2% e pesos 0,5/0,5. Não representa a função de reação do FOMC nem o nível de juros que o Fed deveria adotar.",
  inflation_activity: "O hiato usa PIB real do BEA e PIB potencial estimado pelo CBO. Ambas as séries podem ser revisadas; o modo histórico do painel depende das revisões efetivamente preservadas pelo monitor.",
  treasuries: "As taxas dos títulos do Tesouro dos EUA são preços de mercado. A inflação implícita de 10 anos incorpora prêmios de risco e liquidez; não é uma previsão pura de inflação.",
  br_us: "Os diferenciais Brasil–EUA são comparações descritivas. O diferencial real de 10 anos usa a ETTJ real ANBIMA; o nominal ficará indisponível até a adoção da PRE/B3. Nenhum deles deve ser interpretado isoladamente como risco-país.",
};

function displayLabel(label, key = null) {
  const byKey = {
    "us.policy.effr": "Taxa efetiva dos EUA (EFFR)",
    "us.treasury.2y": "Tesouro dos EUA · 2 anos",
    "us.treasury.10y": "Tesouro dos EUA · 10 anos",
    "us.treasury.real_10y": "Tesouro dos EUA real · 10 anos",
    "us.inflation.breakeven_10y": "Inflação implícita EUA · 10 anos",
    "us.treasury.slope_10y_2y": "Inclinação Tesouro EUA 10a−2a",
  };
  if (key && byKey[key]) return byKey[key];
  return String(label ?? "")
    .replaceAll("Treasury", "Tesouro dos EUA")
    .replaceAll("Breakeven", "Inflação implícita")
    .replaceAll("Federal Funds Effective Rate", "Taxa efetiva dos EUA (EFFR)");
}

function metricCard(indicator, style) {
  const card=document.createElement("button"); card.type="button"; card.className="credit-metric us-metric";
  const label=document.createElement("span"); label.textContent=displayLabel(indicator.label, indicator.key);
  const value=document.createElement("strong"); value.textContent=indicator.latest ? formatUnitValue(Number(indicator.latest.value), indicator.unit) : "—";
  const ref=document.createElement("small"); ref.textContent=indicator.latest ? `Ref. ${formatDate(indicator.latest.date)} · detalhes` : "Indisponível · detalhes";
  card.append(label,value,ref); card.addEventListener("click",()=>openIndicatorDetails({...indicator,definition:indicator.definition??null,caveats:indicator.caveats??[],inputs:indicator.inputs??[],missing_inputs:indicator.missing_inputs??[],series_style:style})); return card;
}
function legendItem(series,index){const item=document.createElement("span");const line=document.createElement("span");line.className=`legend-line legend-series-${Math.min(index+1,5)}`;item.append(line,displayLabel(series.label, series.key));return item;}
function axisFormatter(value,unit){
  if(!Number.isFinite(value)) return "—";
  if(unit==="percentage_points") return `${value.toLocaleString("pt-BR",{maximumFractionDigits:1})} p.p.`;
  return `${value.toLocaleString("pt-BR",{maximumFractionDigits:1})}%`;
}
function tableRows(tbody,h1,h2,h3,series,formatter){
  const heads=[h1,h2,h3]; heads.forEach((h,i)=>{h.textContent=series[i]?displayLabel(series[i].label, series[i].key):"—";h.hidden=!series[i];});
  const maps=series.map(s=>new Map((s.observations??[]).map(x=>[x.date,x]))); const dates=[...new Set(maps.flatMap(m=>[...m.keys()]))].sort().reverse();
  const rows=dates.map(d=>{const row=document.createElement("tr");const dc=document.createElement("td");dc.textContent=formatDate(d);row.append(dc);maps.forEach((m,i)=>{const c=document.createElement("td");const x=m.get(d);c.textContent=x?formatter(Number(x.value)):"—";c.hidden=!series[i];row.append(c);});return row;}); renderPaginatedRows(tbody,rows);
}
export function renderUSUnavailable(message){document.querySelector("#us-unavailable").hidden=false;document.querySelector("#us-unavailable").textContent=message;document.querySelector("#us-content").hidden=true;document.querySelector("#us-date").textContent="Dados ainda não carregados";}
export function renderUS(payload){
  if(!payload||payload.status!=="available"){renderUSUnavailable("Execute ./scripts/update-us.sh para carregar as referências dos EUA.");return;}
  document.querySelector("#us-unavailable").hidden=true;document.querySelector("#us-content").hidden=false;document.querySelector("#us-date").textContent=payload.latest_reference?`Última referência ${formatDate(payload.latest_reference)}`:"Referência indisponível";
  const modes=document.querySelector("#us-mode-controls"),ranges=document.querySelector("#us-range-controls"),metrics=document.querySelector("#us-metrics"),legend=document.querySelector("#us-legend"),note=document.querySelector("#us-note"),chart=document.querySelector("#us-chart"),tbody=document.querySelector("#us-table-body");
  const heads=[document.querySelector("#us-table-head-1"),document.querySelector("#us-table-head-2"),document.querySelector("#us-table-head-3")]; let mode="policy",range=DEFAULT_RANGES.us,handle=null; setRangeControlState(ranges,"data-us-range",range);
  const rerender=()=>{const group=payload.groups[mode];if(!group)return;const anchor=group.chart_series.map(s=>s.latest?.date).filter(Boolean).sort().at(-1)??null;const displayed=group.chart_series.map(s=>({...s,observations:s.status==="available"?filterByRange(s.observations??[],range,anchor):[]}));const unit=group.chart_series[0]?.unit??"percent_per_year";const formatter=(v)=>formatUnitValue(v,unit);metrics.replaceChildren(...group.metrics.map((x,i)=>metricCard(x,`series-${Math.min(i+1,5)}`)));legend.replaceChildren(...group.chart_series.map(legendItem));note.textContent=NOTES[mode]??"";handle?.destroy();handle=renderExternalChart(chart,{series:displayed,valueFormatter:formatter,axisValueFormatter:(v)=>axisFormatter(v,unit)});tableRows(tbody,...heads,displayed.slice(0,3),formatter);};
  modes.addEventListener("click",e=>{const b=e.target.closest("button[data-us-mode]");if(!b)return;mode=b.dataset.usMode;modes.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));rerender();});
  ranges.addEventListener("click",e=>{const b=e.target.closest("button[data-us-range]");if(!b)return;range=b.dataset.usRange;ranges.querySelectorAll("button").forEach(x=>x.setAttribute("aria-pressed",String(x===b)));rerender();});
  rerender();
}
