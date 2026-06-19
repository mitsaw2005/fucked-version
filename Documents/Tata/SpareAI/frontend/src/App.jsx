import React, { useState, useEffect, useMemo, useRef } from "react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine, LabelList,
  ComposedChart
} from "recharts";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// ── Design Tokens ─────────────────────────────────────────
const T = {
  blue:    "#003087",
  blue2:   "#0055b3",
  gold:    "#e8a000",
  green:   "#16a34a",
  red:     "#dc2626",
  orange:  "#d97706",
  gray50:  "#f8fafc",
  gray100: "#f1f5f9",
  gray200: "#e2e8f0",
  gray400: "#94a3b8",
  gray600: "#475569",
  gray900: "#0f172a",
};

const SHOP_COLORS  = [T.blue,"#0891b2","#0d9488",T.gold,"#8b5cf6","#db2777"];
const MAT_COLORS   = [T.blue,"#0891b2","#0d9488","#7c3aed","#db2777","#ea580c","#65a30d",T.gold,T.red,"#4f46e5"];
const ABC_COLORS   = { A: T.red, B: T.orange, C: T.green };
const RISK_CFG     = {
  High:   { bg:"#fef2f2", border:"#fca5a5", text:T.red,    dot:"#ef4444", label:"High Risk"  },
  Medium: { bg:"#fffbeb", border:"#fcd34d", text:T.orange, dot:"#f59e0b", label:"Med Risk"   },
  Low:    { bg:"#f0fdf4", border:"#86efac", text:T.green,  dot:"#22c55e", label:"Low Risk"   },
};
const FONTS = `@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap');`;

// ── Utils ─────────────────────────────────────────────────
const isFiniteNum = val => val != null && !isNaN(val) && Number.isFinite(Number(val));
const fmt  = n => !isFiniteNum(n) ? "" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const fmtD = n => !isFiniteNum(n) ? "" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
const fmtDisplay = n => !isFiniteNum(n) ? "—" : Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 });
const fmtK = n => {
  if (!isFiniteNum(n)) return "—";
  const val = Number(n);
  if (Math.abs(val) >= 100000) return (val/100000).toFixed(1)+"L";
  if (Math.abs(val) >= 1000)   return (val/1000).toFixed(1)+"K";
  return fmt(val);
};
const formatXAxisDate = (dateStr) => {
  if (!dateStr) return "";
  const parts = dateStr.split("-");
  if (parts.length < 2) return dateStr;
  const yr = parts[0];
  const moIdx = parseInt(parts[1], 10) - 1;
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${monthNames[moIdx] || parts[1]} ${yr}`;
};

// ── Base Components ───────────────────────────────────────
function Card({ children, style={}, p=20 }) {
  return (
    <div style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:10,
      padding:p, boxShadow:"0 1px 4px rgba(0,0,0,0.05)", ...style }}>
      {children}
    </div>
  );
}

function CardTitle({ title, sub, right }) {
  return (
    <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:14 }}>
      <div>
        <div style={{ fontSize:13, fontWeight:700, color:T.gray900 }}>{title}</div>
        {sub && <div style={{ fontSize:11, color:T.gray400, marginTop:2 }}>{sub}</div>}
      </div>
      {right}
    </div>
  );
}

function Section({ children }) {
  return (
    <div style={{ display:"flex", alignItems:"center", gap:10, margin:"22px 0 12px" }}>
      <div style={{ width:4, height:18, background:T.blue, borderRadius:2 }} />
      <span style={{ fontSize:10, fontWeight:700, letterSpacing:"0.1em", textTransform:"uppercase", color:T.gray600 }}>{children}</span>
      <div style={{ flex:1, height:1, background:T.gray200 }} />
    </div>
  );
}

function RiskBadge({ level, size=11 }) {
  const c = RISK_CFG[level] || RISK_CFG.Low;
  return (
    <span style={{ background:c.bg, border:`1px solid ${c.border}`, color:c.text,
      borderRadius:999, padding:"3px 10px", fontSize:size, fontWeight:700,
      display:"inline-flex", alignItems:"center", gap:5, whiteSpace:"nowrap" }}>
      <span style={{ width:6, height:6, borderRadius:"50%", background:c.dot, flexShrink:0 }} />
      {c.label}
    </span>
  );
}

function ABCBadge({ cls }) {
  const colors = { A:{bg:"#fef2f2",text:T.red}, B:{bg:"#fffbeb",text:T.orange}, C:{bg:"#f0fdf4",text:T.green} };
  const c = colors[cls] || colors.C;
  return (
    <span style={{ background:c.bg, color:c.text, borderRadius:6, padding:"2px 9px",
      fontSize:11, fontWeight:700, fontFamily:"'IBM Plex Mono'" }}>
      {cls}-Class
    </span>
  );
}

function VendorBadge({ valType }) {
  const isImport = valType === 2 || String(valType) === "2";
  return (
    <span style={{
      background: isImport ? "#eff6ff" : "#f0fdf4",
      color:      isImport ? T.blue2   : T.green,
      border:     `1px solid ${isImport ? "#bfdbfe" : "#86efac"}`,
      borderRadius:6, padding:"2px 9px", fontSize:10, fontWeight:700,
      fontFamily:"'IBM Plex Mono'", whiteSpace:"nowrap"
    }}>
      {isImport ? "✈ Import" : "🏭 Local"}
    </span>
  );
}

// Custom drop-down style matching design tokens
function Sel({ value, onChange, options, style={} }) {
  return (
    <select value={value} onChange={e=>onChange(e.target.value)}
      style={{ background:T.gray50, border:`1px solid ${T.gray200}`, borderRadius:6,
        padding:"6px 10px", fontSize:12, color:T.gray900,
        fontFamily:"'IBM Plex Mono'", outline:"none", cursor:"pointer", ...style }}>
      {options.map(o=><option key={o.value??o} value={o.value??o}>{o.label??o}</option>)}
    </select>
  );
}

function MaterialSearch({ value, onChange, materials, placeholder, allowClear }) {
  const [query, setQuery]   = useState(value || "");
  const [open,  setOpen]    = useState(false);
  const ref                 = useRef();

  useEffect(()=>{ setQuery(value || ""); },[value]);
  useEffect(()=>{
    const handler = e => { if(ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", handler);
    return ()=>document.removeEventListener("mousedown", handler);
  },[]);

  const filtered = useMemo(()=>{
    if(!query) return materials.slice(0,20);
    return materials.filter(m=>m.toLowerCase().includes(query.toLowerCase())).slice(0,20);
  },[query, materials]);

  return (
    <div ref={ref} style={{ position:"relative", minWidth:200 }}>
      <div style={{ position:"relative" }}>
        <input
          value={query}
          onChange={e=>{ setQuery(e.target.value); setOpen(true); }}
          onFocus={()=>setOpen(true)}
          placeholder={placeholder || "Search material..."}
          style={{ width:"100%", background:T.gray50, border:`1px solid ${T.gray200}`,
            borderRadius:6, padding:"7px 12px", paddingRight: allowClear && query ? 30 : 12,
            fontSize:13, color:T.gray900,
            fontFamily:"'IBM Plex Mono'", outline:"none" }}
        />
        {allowClear && query && (
          <button
            onMouseDown={(e) => { e.preventDefault(); setQuery(""); onChange(""); setOpen(false); }}
            style={{ position:"absolute", right:8, top:"50%", transform:"translateY(-50%)",
              background:"none", border:"none", cursor:"pointer", color:T.gray400,
              fontSize:14, fontWeight:700, lineHeight:1, padding:"2px 4px" }}
            title="Clear filter (show all)"
          >✕</button>
        )}
      </div>
      {open && filtered.length > 0 && (
        <div style={{ position:"absolute", top:"100%", left:0, right:0, zIndex:999,
          background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:8,
          boxShadow:"0 8px 24px rgba(0,0,0,0.12)", maxHeight:260, overflowY:"auto", marginTop:4 }}>
          {filtered.map(m=>(
            <div key={m}
              onMouseDown={()=>{ onChange(m); setQuery(m); setOpen(false); }}
              style={{ padding:"9px 14px", fontSize:12, color:T.gray900, cursor:"pointer",
                fontFamily:"'IBM Plex Mono'", borderBottom:`1px solid ${T.gray100}`,
                background: m===value ? T.gray50 : "#fff" }}
              onMouseEnter={e=>e.currentTarget.style.background=T.gray50}
              onMouseLeave={e=>e.currentTarget.style.background= m===value ? T.gray50 : "#fff"}
            >
              {m}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Delta({ val, suffix="%" }) {
  if(!isFiniteNum(val)) return null;
  const up = val >= 0;
  return (
    <span style={{ fontSize:11, fontWeight:700, color:up?T.red:T.green,
      background:up?"#fef2f2":"#f0fdf4", borderRadius:999,
      padding:"2px 8px", marginLeft:6 }}>
      {up?"▲":"▼"} {Math.abs(val).toFixed(1)}{suffix}
    </span>
  );
}

const AlwaysLabel = (props) => {
  const { x, y, width, value, threshold, useShortFormat } = props;
  if(!isFiniteNum(value)) return null;
  if(threshold != null && value < threshold) return null;
  return (
    <text x={x + width/2} y={y - 5} fill={T.gray600} textAnchor="middle"
      fontSize={9} fontFamily="IBM Plex Mono" fontWeight="bold">
      {useShortFormat ? fmtK(value) : fmt(value)}
    </text>
  );
};

const Tip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:8,
      padding:"10px 14px", boxShadow:"0 4px 16px rgba(0,0,0,0.1)", fontSize:12 }}>
      <div style={{ color:T.gray400, fontSize:11, marginBottom:4, fontFamily:"'IBM Plex Mono'" }}>{label}</div>
      {payload.map((p,i)=>(
        <div key={i} style={{ color:p.color||T.gray900, fontWeight:600 }}>{p.name}: {fmt(p.value)}</div>
      ))}
    </div>
  );
};

const LabelDot = (props) => {
  const { cx, cy, value, index, data } = props;
  if(!cx || !cy || !isFiniteNum(value)) return null;
  const total = data?.length || 1;
  const step  = Math.max(1, Math.floor(total / 8));
  if(index % step !== 0 && index !== total-1) return null;
  return (
    <g>
      <circle cx={cx} cy={cy} r={3} fill={props.stroke||T.blue} />
      <text x={cx} y={cy-8} textAnchor="middle" fontSize={9}
        fill={T.gray600} fontFamily="IBM Plex Mono">
        {fmtK(value)}
      </text>
    </g>
  );
};

function HBar({ label, value, max, color, rank, onClick }) {
  const pct = max > 0 ? (Math.abs(value)/max)*100 : 0;
  return (
    <div
      onClick={onClick}
      style={{
        display:"flex",
        alignItems:"center",
        gap:8,
        marginBottom:7,
        cursor: onClick ? "pointer" : "default",
        padding: "3px 6px",
        borderRadius: 6,
        transition: "all 0.2s"
      }}
      onMouseEnter={e => { if (onClick) e.currentTarget.style.background = T.gray100; }}
      onMouseLeave={e => { if (onClick) e.currentTarget.style.background = "transparent"; }}
    >
      {rank && <span style={{ width:16, fontSize:10, color:T.gray400, fontFamily:"'IBM Plex Mono'", textAlign:"right", flexShrink:0 }}>{rank}</span>}
      <span style={{ width:72, fontSize:11, color:T.gray600, flexShrink:0, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap", textAlign:"right", fontFamily:"'IBM Plex Mono'" }}>{label}</span>
      <div style={{ flex:1, height:7, background:T.gray100, borderRadius:4, overflow:"hidden" }}>
        <div style={{ width:`${pct}%`, height:"100%", background:color, borderRadius:4, transition:"width 0.5s" }} />
      </div>
      <span style={{ width:75, fontSize:11, color:T.gray600, textAlign:"right", fontFamily:"'IBM Plex Mono'", flexShrink:0 }}>{fmt(Math.abs(value))}</span>
    </div>
  );
}


// ═══════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════
export default function App() {
  const [tab, setTab]                     = useState("overview");
  const [plantSummary, setPlantSummary]   = useState(null);
  const [procurement, setProcurement]     = useState([]);
  const [alerts, setAlerts]               = useState([]);
  const [materials, setMaterials]         = useState([]);
  const [topMats, setTopMats]             = useState([]);
  const [shopData, setShopData]           = useState([]);
  const [shopMonthly, setShopMonthly]     = useState([]);
  const [allShopMonthly, setAllShopMonthly] = useState([]);
  const [abcData, setAbcData]             = useState([]);
  const [years, setYears]                 = useState([]);
  const [dataYear, setDataYear]           = useState("");
  const [dashboardValidation, setDashboardValidation] = useState(null);
  const [forecastEngine, setForecastEngine]         = useState(null);
  const [yearMetadata, setYearMetadata]             = useState({});
  const [selected, setSelected]           = useState("");
  const [matDetail, setMatDetail]         = useState(null);
  const [history, setHistory]             = useState([]);
  const [loading, setLoading]             = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [selectedShop, setSelectedShop]   = useState("all");
  const [expandedProcurementRows, setExpandedProcurementRows] = useState({});
  const [procurementView, setProcurementView] = useState("shop");
  const [shopView, setShopView] = useState("monthly");       // "monthly" | "dayofweek" | "heatmap"
  const [consumptionView, setConsumptionView] = useState("yoy"); // "yoy" | "monthly" | "dayofweek"
  // Multi-select shop filter for Shop Analysis tab (empty set = all shops)
  const [shopChartSel, setShopChartSel] = useState(new Set());

  // ── Morning Meeting state ─────────────────────────────
  const [mmBudget, setMmBudget]           = useState(() => {
    try { return JSON.parse(localStorage.getItem("mm_budget_v1") || "{}"); } catch { return {}; }
  });
  const [mmPin, setMmPin]                 = useState(() => localStorage.getItem("mm_pin") || "");
  const [mmShowBudgetModal, setMmShowBudgetModal] = useState(false);
  const [mmPinInput, setMmPinInput]       = useState("");
  const [mmPinError, setMmPinError]       = useState("");
  const [mmPinStep, setMmPinStep]         = useState("locked"); // "locked"|"verify"|"edit"|"setpin"
  const [mmBudgetDraft, setMmBudgetDraft] = useState({});
  const [mmNewPin, setMmNewPin]           = useState("");
  const [mmNewPinConfirm, setMmNewPinConfirm] = useState("");
  const [mmAllMonthly, setMmAllMonthly]   = useState([]);
  const [mmLoadingAll, setMmLoadingAll]   = useState(false);

  // Filters
  const [riskFilter,       setRiskFilter]      = useState("High");
  const [abcFilter,        setAbcFilter]       = useState("all");
  const [shopFilter,       setShopFilter]      = useState("all");
  const [materialFilter,   setMaterialFilter]  = useState("all");
  const [trendYears,       setTrendYears]      = useState([]);
  const [trendMonth,       setTrendMonth]      = useState("all");
  const [shopYear,         setShopYear]        = useState("");
  const [shopMonth,        setShopMonth]       = useState("all");
  const [trendYear,        setTrendYear]       = useState("all");

  const MONTHS = [
    {value:"all",label:"All Months"},{value:"01",label:"Jan"},{value:"02",label:"Feb"},
    {value:"03",label:"Mar"},{value:"04",label:"Apr"},{value:"05",label:"May"},{value:"06",label:"Jun"},
    {value:"07",label:"Jul"},{value:"08",label:"Aug"},{value:"09",label:"Sep"},
    {value:"10",label:"Oct"},{value:"11",label:"Nov"},{value:"12",label:"Dec"},
  ];

  useEffect(()=>{
    setLoading(true);
    Promise.all([
      fetch(`${API}/years`).then(r=>r.json()),
      fetch(`${API}/procurement-summary`).then(r=>r.json()),
      fetch(`${API}/critical-alerts`).then(r=>r.json()),
      fetch(`${API}/materials`).then(r=>r.json()),
    ]).then(([yr,proc,al,mats])=>{
      setProcurement(proc);
      setAlerts(al);
      const matList = mats.materials||[];
      setMaterials(matList);
      if(matList.length) setSelected(matList[0]);
      const yearList = (yr.years || []).map(String);
      const latest = String(yr.latest_year || yearList[yearList.length - 1] || "");
      const metaMap = {};
      (yr.all_years_metadata || []).forEach(m => { metaMap[String(m.year)] = m; });
      setYearMetadata(metaMap);
      setYears(yearList);
      setDataYear(latest);
      setTrendYears(latest ? [latest] : []);
      setShopYear(latest);
      if(!latest) setLoading(false);
    }).catch(()=>setLoading(false));
  },[]);

  useEffect(()=>{
    if(!dataYear) return;
    setLoading(true);
    const yearParam = encodeURIComponent(dataYear);
    Promise.all([
      fetch(`${API}/plant-summary?year=${yearParam}`).then(r=>r.json()),
      fetch(`${API}/top-materials?year=${yearParam}`).then(r=>r.json()),
      fetch(`${API}/shop-consumption?year=${yearParam}`).then(r=>r.json()),
      fetch(`${API}/abc-analysis?year=${yearParam}`).then(r=>r.json()),
      fetch(`${API}/shop-monthly?year=${yearParam}`).then(r=>r.json()),
    ]).then(([ps,tm,sd,abc,sm])=>{
      setPlantSummary(ps);
      setTopMats(tm);
      setShopData(sd);
      setAbcData(abc);
      setShopMonthly(sm.records || sm);
      if(sm.year_metadata) {
        setYearMetadata(prev => ({ ...prev, [String(sm.year_metadata.year)]: sm.year_metadata }));
      }
      setLoading(false);
    }).catch(()=>setLoading(false));
  },[dataYear]);

  useEffect(()=>{
    if(tab !== "consumption" || allShopMonthly.length) return;
    Promise.all(years.map(y =>
      fetch(`${API}/shop-monthly?year=${encodeURIComponent(y)}`).then(r=>r.json())
    )).then(results => {
      const combined = results.flatMap(r => r.records || r);
      setAllShopMonthly(combined);
    }).catch(()=>{});
  },[tab, years, allShopMonthly.length]);

  useEffect(()=>{
    if(tab !== "developer" || !dataYear) return;
    const yearParam = encodeURIComponent(dataYear);
    Promise.all([
      fetch(`${API}/dashboard-validation?year=${yearParam}`).then(r=>r.json()),
      fetch(`${API}/forecast-engine`).then(r=>r.json()),
    ]).then(([validation, engine])=>{
      setDashboardValidation(validation);
      setForecastEngine(engine);
    }).catch(()=>{});
  },[tab, dataYear]);



  useEffect(()=>{
    if(!selected) return;
    setDetailLoading(true);
    Promise.all([
      fetch(`${API}/forecast/${selected}`).then(r=>r.json()),
      fetch(`${API}/history/${selected}`).then(r=>r.json()),
    ]).then(([f,h])=>{
      setMatDetail(f);
      setHistory(h.map(r=>({
        date:  r["pstng date"]?.slice(0,7),
        qty:   +Number(r.Quantity).toFixed(2),
        year:  r["pstng date"]?.slice(0,4),
        month: r["pstng date"]?.slice(5,7),
      })));
      setDetailLoading(false);
    }).catch(()=>setDetailLoading(false));
  },[selected]);

  // ── Morning Meeting: fetch ALL years' shop-monthly when tab opens ──
  useEffect(()=>{
    if(tab !== "morning" || mmAllMonthly.length || mmLoadingAll) return;
    setMmLoadingAll(true);
    Promise.all(years.map(y =>
      fetch(`${API}/shop-monthly?year=${encodeURIComponent(y)}`).then(r=>r.json())
    )).then(results => {
      const combined = results.flatMap(r => r.records || r);
      setMmAllMonthly(combined);
      setMmLoadingAll(false);
    }).catch(()=>setMmLoadingAll(false));
  },[tab, years, mmAllMonthly.length, mmLoadingAll]);

  // ── Morning Meeting computed ──────────────────────────
  const mmShops = useMemo(()=>{
    const src = mmAllMonthly.length ? mmAllMonthly : (allShopMonthly.length ? allShopMonthly : shopMonthly);
    return [...new Set(src.map(r=>r.Shop).filter(Boolean))].sort();
  },[mmAllMonthly, allShopMonthly, shopMonthly]);

  // Determine current FY: Apr-Mar cycle
  const today = new Date();
  const mmFYStart = today.getMonth() >= 3
    ? new Date(today.getFullYear(), 3, 1)   // Apr this year
    : new Date(today.getFullYear()-1, 3, 1); // Apr last year
  const mmFYEnd   = new Date(mmFYStart.getFullYear()+1, 2, 31); // Mar 31 next year
  const mmFYLabel = `FY${String(mmFYStart.getFullYear()).slice(2)}-${String(mmFYEnd.getFullYear()).slice(2)}`;

  // Yesterday label
  const mmYesterday = new Date(today); mmYesterday.setDate(today.getDate()-1);
  const mmYesterdayLabel = `${String(mmYesterday.getDate()).padStart(2,"0")}.${String(mmYesterday.getMonth()+1).padStart(2,"0")}.${mmYesterday.getFullYear()}`;

  // Generate all FY months in reverse (newest first)
  const mmFYMonths = useMemo(()=>{
    const months = [];
    let d = new Date(mmFYStart);
    while (d <= mmFYEnd && d <= today) {
      months.push(`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`);
      d.setMonth(d.getMonth()+1);
    }
    return months.reverse(); // newest first
  },[mmFYStart.getTime()]);

  // Consumption matrix: { [monthStr]: { [shop]: qty, total: qty } }
  const mmMatrix = useMemo(()=>{
    const src = mmAllMonthly.length ? mmAllMonthly : (allShopMonthly.length ? allShopMonthly : shopMonthly);
    const mat = {};
    src.forEach(r=>{
      if (!r.month_str || !r.Shop) return;
      if (!mat[r.month_str]) mat[r.month_str] = { total: 0 };
      mat[r.month_str][r.Shop] = (mat[r.month_str][r.Shop]||0) + r.Quantity;
      mat[r.month_str].total   = (mat[r.month_str].total||0)   + r.Quantity;
    });
    return mat;
  },[mmAllMonthly, allShopMonthly, shopMonthly]);

  // Yesterday's data: sum of latest available day (proxy: last month's daily avg)
  const mmYesterdayRow = useMemo(()=>{
    // Use most recent month data divided by days in that month as proxy
    if (!mmFYMonths.length) return {};
    const latestMonth = mmFYMonths[0];
    const monthData = mmMatrix[latestMonth] || {};
    const [yr, mo] = latestMonth.split("-").map(Number);
    const daysInMonth = new Date(yr, mo, 0).getDate();
    const result = { total: 0 };
    mmShops.forEach(s => {
      const daily = Math.round((monthData[s]||0) / daysInMonth);
      result[s] = daily;
      result.total += daily;
    });
    return result;
  },[mmMatrix, mmFYMonths, mmShops]);

  // Months elapsed in FY (for YTD budget proration)
  const mmMonthsElapsed = useMemo(()=>{
    const now = new Date();
    const fyStart = mmFYStart;
    const months = (now.getFullYear()-fyStart.getFullYear())*12 + (now.getMonth()-fyStart.getMonth()) + 1;
    return Math.min(months, 12);
  },[mmFYStart.getTime()]);

  // YTD sums
  const mmYTD = useMemo(()=>{
    const result = { total: 0 };
    mmShops.forEach(s => result[s] = 0);
    mmFYMonths.forEach(m => {
      const row = mmMatrix[m] || {};
      mmShops.forEach(s => {
        result[s] = (result[s]||0) + (row[s]||0);
        result.total += (row[s]||0);
      });
    });
    return result;
  },[mmMatrix, mmFYMonths, mmShops]);

  // Budget helpers
  const mmSaveBudget = (draft) => {
    setMmBudget(draft);
    localStorage.setItem("mm_budget_v1", JSON.stringify(draft));
  };
  const mmSavePin = (pin) => {
    setMmPin(pin);
    localStorage.setItem("mm_pin", pin);
  };
  const mmGetAnnualBudget = (shop) => Number(mmBudget[shop] || 0);
  const mmGetMonthlyBudget = (shop) => mmGetAnnualBudget(shop) / 12;
  const mmGetTotalAnnualBudget = () => mmShops.reduce((s,sh)=>s+mmGetAnnualBudget(sh),0);
  const mmGetYTDBudget = (shop) => mmGetMonthlyBudget(shop) * mmMonthsElapsed;

  // ── Derived ───────────────────────────────────────────
  const currentYear = String(dataYear || plantSummary?.latest_year || "");

  const filteredProcurement = useMemo(()=>{
    let d = [...procurement];
    if(riskFilter !== "all") d = d.filter(r=>r.risk === riskFilter);
    if(abcFilter  !== "all") d = d.filter(r=>r.abc_class === abcFilter);
    if(shopFilter !== "all") d = d.filter(r=>r.shop === shopFilter);
    if(materialFilter !== "all") d = d.filter(r=>r.material === materialFilter);
    d.sort((a,b)=>(a.lead_time?.days_to_runout??999)-(b.lead_time?.days_to_runout??999));
    return d;
  },[procurement, riskFilter, abcFilter, shopFilter, materialFilter]);

  // Consolidated procurement — group by material, aggregate across shops
  const consolidatedProcurement = useMemo(() => {
    const groups = {};
    procurement.forEach(r => {
      const mat = r.material;
      if (!groups[mat]) {
        groups[mat] = {
          material: mat,
          shops: [],
          rows: [],
          total_order_qty: 0,
          total_recommended_qty: 0,
          total_current_stock: 0,
          total_30d: 0, total_60d: 0, total_90d: 0,
          min_days_left: Infinity,
          highest_risk: "Low",
          abc_class: r.abc_class,
          lead_time: r.lead_time,
          forecast_source: r.forecast?.forecast_source,
          safety_stock: 0,
          reorder_by: r.lead_time?.reorder_by,
        };
      }
      const g = groups[mat];
      if (!g.shops.includes(r.shop)) g.shops.push(r.shop);
      g.rows.push(r);
      g.total_order_qty += (r.order?.order_qty || 0);
      g.total_recommended_qty += (r.order?.recommended_qty || 0);
      g.total_current_stock += (r.inventory?.current_stock || 0);
      g.total_30d += (r.forecast?.forecast_30d || 0);
      g.total_60d += (r.forecast?.forecast_60d || 0);
      g.total_90d += (r.forecast?.forecast_90d || 0);
      g.safety_stock += (r.inventory?.safety_stock || 0);
      const daysLeft = r.lead_time?.days_to_runout ?? 999;
      if (daysLeft < g.min_days_left) g.min_days_left = daysLeft;
      const riskOrder = { High: 3, Medium: 2, Low: 1 };
      if ((riskOrder[r.risk] || 0) > (riskOrder[g.highest_risk] || 0)) {
        g.highest_risk = r.risk;
      }
      if (r.lead_time?.reorder_by && (!g.reorder_by || r.lead_time.reorder_by < g.reorder_by)) {
        g.reorder_by = r.lead_time.reorder_by;
      }
    });
    return Object.values(groups).sort((a, b) => a.min_days_left - b.min_days_left);
  }, [procurement]);

  // Filtered consolidated view
  const filteredConsolidated = useMemo(() => {
    let d = [...consolidatedProcurement];
    if (riskFilter !== "all") d = d.filter(r => r.highest_risk === riskFilter);
    if (abcFilter !== "all") d = d.filter(r => r.abc_class === abcFilter);
    if (shopFilter !== "all") d = d.filter(r => r.shops.includes(shopFilter));
    if (materialFilter !== "all") d = d.filter(r => r.material === materialFilter);
    return d;
  }, [consolidatedProcurement, riskFilter, abcFilter, shopFilter, materialFilter]);

  // Multi-shop materials for developer validation
  const multiShopMaterials = useMemo(() => {
    return consolidatedProcurement
      .filter(c => c.shops.length > 1)
      .sort((a, b) => b.shops.length - a.shops.length);
  }, [consolidatedProcurement]);

  // Material deep dive history filtered
  const filteredHistory = useMemo(()=>{
    let d = history.filter(r => r.year === currentYear);
    if(trendYear  !== "all") d = history.filter(r=>r.year  === trendYear);
    if(trendMonth !== "all") d = d.filter(r=>r.month === trendMonth);
    return d;
  },[history, currentYear, trendYear, trendMonth]);

  const histYears = useMemo(()=>["all",...new Set(history.map(r=>r.year))].sort(),[history]);
  const shops     = useMemo(()=>["all",...new Set(procurement.map(r=>r.shop).filter(Boolean))],[procurement]);

  // Shop monthly pivot — selected year by default
  const shopMonthlyPivot = useMemo(()=>{
    let d = shopMonthly;
    if(shopYear  !== "all") d = d.filter(r=>r.month_str?.startsWith(shopYear));
    if(shopMonth !== "all") d = d.filter(r=>r.month_str?.slice(5,7) === shopMonth);
    const pivot = {};
    d.forEach(r=>{
      if(!pivot[r.month_str]) pivot[r.month_str] = { month: r.month_str };
      pivot[r.month_str][r.Shop] = (pivot[r.month_str][r.Shop]||0) + r.Quantity;
    });
    return Object.values(pivot).sort((a,b)=>a.month.localeCompare(b.month));
  },[shopMonthly, shopYear, shopMonth]);

  const shopNames    = useMemo(()=>[...new Set(shopMonthly.map(r=>r.Shop).filter(Boolean))],[shopMonthly]);
  const allYearsShop = useMemo(()=>["all",...new Set(shopMonthly.map(r=>r.month_str?.slice(0,4)).filter(Boolean))].sort(),[shopMonthly]);

  // Shop stats — selected year by default
  const shopStats = useMemo(()=>{
    if(!shopMonthly.length) return {};
    const statYear = shopYear === "all" ? null : (shopYear || currentYear);
    const curYear = statYear ? shopMonthly.filter(r=>r.month_str?.startsWith(statYear)) : shopMonthly;
    const base    = curYear.length ? curYear : shopMonthly;
    const sorted  = [...new Set(base.map(r=>r.month_str))].sort();
    const lastM   = sorted[sorted.length-1];
    const prevM   = sorted[sorted.length-2];
    const stats   = {};
    shopData.forEach(s=>{
      const thisMonth = base.filter(r=>r.month_str===lastM && r.Shop===s.Shop).reduce((a,r)=>a+r.Quantity,0);
      const prevMonth = base.filter(r=>r.month_str===prevM && r.Shop===s.Shop).reduce((a,r)=>a+r.Quantity,0);
      const avgAll    = base.filter(r=>r.Shop===s.Shop).reduce((a,r)=>a+r.Quantity,0) /
                        Math.max([...new Set(base.filter(r=>r.Shop===s.Shop).map(r=>r.month_str))].length,1);
      const delta     = prevMonth > 0 ? ((thisMonth-prevMonth)/prevMonth)*100 : 0;
      const spike     = avgAll > 0 && thisMonth > avgAll*1.2;
      stats[s.Shop]   = { thisMonth, prevMonth, delta, spike, lastM, avgAll };
    });
    return stats;
  },[shopMonthly, shopData, shopYear, currentYear]);

  const machineByShop = useMemo(()=>{
    const result = {};
    procurement.forEach(r=>{
      if(!r.shop || !r.machine) return;
      if(!result[r.shop]) result[r.shop] = {};
      if(!result[r.shop][r.machine]) result[r.shop][r.machine] = { high:0, medium:0, low:0, total:0 };
      result[r.shop][r.machine][r.risk.toLowerCase()]++;
      result[r.shop][r.machine].total++;
    });
    return result;
  },[procurement]);

  const shopSummaryTableData = useMemo(() => {
    return shopNames.map(name => {
      const consumption = shopData.find(s => s.Shop === name)?.Quantity || 0;
      const criticalRisks = procurement.filter(r => r.shop === name && r.risk === "High").length;
      const mediumRisks = procurement.filter(r => r.shop === name && r.risk === "Medium").length;
      return { shop: name, consumption, criticalRisks, mediumRisks };
    }).sort((a, b) => b.consumption - a.consumption);
  }, [shopNames, shopData, procurement]);

  const activeYearShopMonthly = useMemo(() => {
    let d = shopMonthly.filter(r => r.month_str?.startsWith(currentYear));
    if (selectedShop !== "all") {
      d = d.filter(r => r.Shop === selectedShop);
    }
    const monthlySums = {};
    d.forEach(r => {
      monthlySums[r.month_str] = (monthlySums[r.month_str] || 0) + r.Quantity;
    });
    return Object.entries(monthlySums).map(([monthStr, qty]) => ({
      monthStr,
      qty
    })).sort((a, b) => a.monthStr.localeCompare(b.monthStr));
  }, [shopMonthly, currentYear, selectedShop]);

  const currentMonthConsumption = useMemo(() => {
    if (!activeYearShopMonthly.length) return 0;
    return activeYearShopMonthly[activeYearShopMonthly.length - 1]?.qty || 0;
  }, [activeYearShopMonthly]);

  const peakShopMonth = useMemo(() => {
    if (!activeYearShopMonthly.length) return "—";
    let maxVal = -1;
    let maxDate = "";
    activeYearShopMonthly.forEach(m => {
      if (m.qty > maxVal) {
        maxVal = m.qty;
        maxDate = m.monthStr;
      }
    });
    if (!maxDate) return "—";
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const monthIndex = parseInt(maxDate.slice(5, 7), 10) - 1;
    return `${monthNames[monthIndex]} ${maxDate.slice(0,4)}`;
  }, [activeYearShopMonthly]);

  const shopAtRiskCount = useMemo(() => {
    if (selectedShop === "all") {
      return procurement.filter(r => r.risk !== "Low").length;
    }
    return procurement.filter(r => r.shop === selectedShop && r.risk !== "Low").length;
  }, [procurement, selectedShop]);

  const shopTrendChartData = useMemo(() => {
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return activeYearShopMonthly.map(m => {
      const mIdx = parseInt(m.monthStr.slice(5, 7), 10) - 1;
      return {
        month: monthNames[mIdx] || m.monthStr,
        Quantity: m.qty
      };
    });
  }, [activeYearShopMonthly]);

  const shopTopMaterials = useMemo(() => {
    let mats = [...procurement];
    if (selectedShop !== "all") {
      mats = mats.filter(r => r.shop === selectedShop);
    }
    const sorted = mats
      .map(r => ({
        material: r.material,
        consumption: r.yearly_consumption?.[currentYear] || 0
      }))
      .sort((a, b) => b.consumption - a.consumption);
    const totalShopQty = sorted.reduce((sum, r) => sum + r.consumption, 0);
    return sorted.slice(0, 10).map(r => ({
      material: r.material,
      consumption: r.consumption,
      pct: totalShopQty > 0 ? (r.consumption / totalShopQty) * 100 : 0
    }));
  }, [procurement, selectedShop, currentYear]);

  const shopAtRiskList = useMemo(() => {
    let mats = [...procurement].filter(r => r.risk !== "Low");
    if (selectedShop !== "all") {
      mats = mats.filter(r => r.shop === selectedShop);
    }
    return mats.map(r => ({
      material: r.material,
      daysLeft: r.lead_time?.days_to_runout ?? 999,
      risk: r.risk,
      orderNeeded: r.order?.recommended_qty || 0
    })).sort((a, b) => a.daysLeft - b.daysLeft);
  }, [procurement, selectedShop]);

  // Overview shop/mat data comes directly from /shop-consumption for the selected year
  const shopDataCurrent = useMemo(()=>{
    return shopData;
  },[shopData]);

  const maxShopCurrent = Math.max(...shopDataCurrent.map(s=>s.Quantity||0));

  // YoY data — all years, filtered by trendYears selection
  const allYearsAvailable = useMemo(()=>{
    if(years.length) return years;
    const keys = new Set();
    shopMonthly.forEach(r=>{ if(r.month_str) keys.add(r.month_str.slice(0,4)); });
    return [...keys].sort();
  },[years, shopMonthly]);

  const historicalShopMonthly = allShopMonthly.length ? allShopMonthly : shopMonthly;

  const yoyData = useMemo(()=>{
    if(!historicalShopMonthly.length) return [];
    const byMonthYear = {};
    historicalShopMonthly.forEach(r=>{
      const yr  = r.month_str?.slice(0,4);
      const mo  = r.month_str?.slice(5,7);
      if(!byMonthYear[mo]) byMonthYear[mo] = {};
      byMonthYear[mo][yr] = (byMonthYear[mo][yr]||0) + r.Quantity;
    });
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return Array.from({length:12},(_,i)=>{
      const mo  = String(i+1).padStart(2,"0");
      const row = { month: monthNames[i] };
      (trendYears.length ? trendYears : allYearsAvailable).forEach(yr=>{
        if(byMonthYear[mo]?.[yr] != null) row[yr] = Math.round(byMonthYear[mo][yr]);
      });
      return row;
    });
  },[historicalShopMonthly, trendYears, allYearsAvailable]);

  const yoyYears = useMemo(()=>{
    const keys = new Set();
    yoyData.forEach(row=>Object.keys(row).forEach(k=>{ if(k!=="month") keys.add(k); }));
    return [...keys].sort();
  },[yoyData]);

  // Seasonal pattern — filtered by selected years
  const seasonalData = useMemo(()=>{
    if(!historicalShopMonthly.length) return [];
    const filtered = trendYears.length
      ? historicalShopMonthly.filter(r=>trendYears.includes(r.month_str?.slice(0,4)))
      : historicalShopMonthly;
    const byMonth = {};
    filtered.forEach(r=>{
      const mo = r.month_str?.slice(5,7);
      if(!mo) return;
      if(!byMonth[mo]) byMonth[mo] = [];
      byMonth[mo].push(r.Quantity);
    });
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const avgs = Array.from({length:12},(_,i)=>{
      const mo   = String(i+1).padStart(2,"0");
      const vals = byMonth[mo] || [];
      return vals.length ? vals.reduce((s,v)=>s+v,0)/vals.length : 0;
    });
    const maxAvg = Math.max(...avgs);
    return avgs.map((avg,i)=>({
      month: monthNames[i],
      avg:   Math.round(avg),
      intensity: maxAvg > 0 ? avg/maxAvg : 0,
    }));
  },[historicalShopMonthly, trendYears]);

  // ABC API returns Quantity Consumed for the selected dashboard year.
  const abcDataFiltered = useMemo(()=>{
    return abcData;
  },[abcData]);

  // ── Day-of-week breakdown (Shop Analysis) ─────────────────
  // Approximates day-of-week from monthly data by distributing consumption
  // evenly across ~22 working days. When raw daily data is available from
  // the history endpoint (per-material), we use actual posting dates.
  const shopDayOfWeekData = useMemo(() => {
    const DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    // Use the per-material history records which have actual dates
    // Aggregate across all materials for the selected shop & year
    const counts = Array(7).fill(0);
    const totals = Array(7).fill(0);
    // shopMonthly has month_str + Shop + Quantity — no day info
    // We use activeYearShopMonthly as a proxy: spread qty across business days
    activeYearShopMonthly.forEach(m => {
      const [yr, mo] = m.monthStr.split("-").map(Number);
      const daysInMonth = new Date(yr, mo, 0).getDate();
      const dailyAvg = m.qty / daysInMonth;
      for (let d = 1; d <= daysInMonth; d++) {
        const dow = new Date(yr, mo - 1, d).getDay(); // 0=Sun
        const idx = dow === 0 ? 6 : dow - 1; // Mon=0..Sun=6
        totals[idx] += dailyAvg;
        counts[idx]++;
      }
    });
    return DOW.map((day, i) => ({
      day,
      avg: counts[i] > 0 ? Math.round(totals[i] / (activeYearShopMonthly.length || 1)) : 0,
      total: Math.round(totals[i]),
    }));
  }, [activeYearShopMonthly]);

  // ── Shop Analysis: active shop names based on multi-select ──
  const shopChartActiveNames = useMemo(() => {
    if (shopChartSel.size === 0) return shopNames;
    return shopNames.filter(s => shopChartSel.has(s));
  }, [shopNames, shopChartSel]);

  // ── Shop Analysis: filtered monthly breakdown ──
  const shopMonthlyBreakdownFiltered = useMemo(() => {
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    let src = (allShopMonthly.length ? allShopMonthly : shopMonthly)
      .filter(r => r.month_str?.startsWith(currentYear));
    if (shopChartSel.size > 0) src = src.filter(r => shopChartSel.has(r.Shop));
    const byMonth = {};
    src.forEach(r => {
      const mo = r.month_str?.slice(5,7);
      if (!mo) return;
      const label = monthNames[parseInt(mo,10)-1];
      if (!byMonth[label]) byMonth[label] = { month: label };
      byMonth[label][r.Shop] = (byMonth[label][r.Shop] || 0) + r.Quantity;
    });
    return monthNames.filter(m => byMonth[m]).map(m => byMonth[m]);
  }, [shopMonthly, allShopMonthly, currentYear, shopChartSel]);

  // ── Shop Analysis: filtered DOW with date labels ──
  const shopDayOfWeekFiltered = useMemo(() => {
    const DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    const totals = Array(7).fill(0);
    const counts = Array(7).fill(0);
    const today = new Date();
    const dowDates = Array(7).fill(null);
    for (let back = 0; back < 14; back++) {
      const d = new Date(today); d.setDate(today.getDate() - back);
      const dow = d.getDay();
      const idx = dow === 0 ? 6 : dow - 1;
      if (!dowDates[idx]) dowDates[idx] = String(d.getDate()).padStart(2,"0") + "/" + String(d.getMonth()+1).padStart(2,"0");
    }
    let base = (allShopMonthly.length ? allShopMonthly : shopMonthly)
      .filter(r => r.month_str?.startsWith(currentYear));
    if (shopChartSel.size > 0) base = base.filter(r => shopChartSel.has(r.Shop));
    base.forEach(m => {
      const parts = (m.month_str || "").split("-").map(Number);
      const yr = parts[0]; const mo = parts[1];
      if (!yr || !mo) return;
      const daysInMonth = new Date(yr, mo, 0).getDate();
      const dailyAvg = m.Quantity / daysInMonth;
      for (let d = 1; d <= daysInMonth; d++) {
        const dow = new Date(yr, mo - 1, d).getDay();
        const idx = dow === 0 ? 6 : dow - 1;
        totals[idx] += dailyAvg;
        counts[idx]++;
      }
    });
    return DOW.map((day, i) => ({
      day,
      tickLabel: dowDates[i] ? day + " " + dowDates[i] : day,
      avg: counts[i] > 0 ? Math.round(totals[i] / (base.length || 1)) : 0,
      total: Math.round(totals[i]),
    }));
  }, [shopMonthly, allShopMonthly, currentYear, shopChartSel]);

  // ── Maximum Values for clean chart labeling ──
  const maxShopBreakdownVal = useMemo(() => {
    if (!shopMonthlyBreakdownFiltered.length) return 0;
    let maxVal = 0;
    shopMonthlyBreakdownFiltered.forEach(row => {
      shopChartActiveNames.forEach(shop => {
        if (row[shop] > maxVal) maxVal = row[shop];
      });
    });
    return maxVal;
  }, [shopMonthlyBreakdownFiltered, shopChartActiveNames]);

  const maxShopDayOfWeekVal = useMemo(() => {
    if (!shopDayOfWeekFiltered.length) return 0;
    return Math.max(...shopDayOfWeekFiltered.map(x => x.avg || 0));
  }, [shopDayOfWeekFiltered]);

  const maxYoyVal = useMemo(() => {
    if (!yoyData.length) return 0;
    let maxVal = 0;
    yoyData.forEach(row => {
      yoyYears.forEach(yr => {
        if (row[yr] > maxVal) maxVal = row[yr];
      });
    });
    return maxVal;
  }, [yoyData, yoyYears]);

  const maxSeasonalVal = useMemo(() => {
    if (!seasonalData.length) return 0;
    return Math.max(...seasonalData.map(x => x.avg || 0));
  }, [seasonalData]);

  const maxAbcVal = useMemo(() => {
    if (!abcDataFiltered.length) return 0;
    return Math.max(...abcDataFiltered.map(x => x.total_qty || 0));
  }, [abcDataFiltered]);


  // ── Monthly breakdown per shop (stacked bars for Shop Analysis) ──
  const shopMonthlyBreakdown = useMemo(() => {
    // For each month in current year, show each shop's contribution
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const byMonth = {};
    let sourceData = allShopMonthly.length ? allShopMonthly : shopMonthly;
    sourceData.filter(r => r.month_str?.startsWith(currentYear)).forEach(r => {
      const mo = r.month_str?.slice(5,7);
      if (!mo) return;
      const label = monthNames[parseInt(mo,10)-1];
      if (!byMonth[label]) byMonth[label] = { month: label };
      byMonth[label][r.Shop] = (byMonth[label][r.Shop] || 0) + r.Quantity;
    });
    const moOrder = monthNames;
    return moOrder.filter(m => byMonth[m]).map(m => byMonth[m]);
  }, [shopMonthly, allShopMonthly, currentYear]);

  // ── Monthly heatmap data (shop × month matrix for Shop Analysis) ──
  const shopHeatmapData = useMemo(() => {
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    const matrix = {};
    let sourceData = allShopMonthly.length ? allShopMonthly : shopMonthly;
    sourceData.filter(r => r.month_str?.startsWith(currentYear)).forEach(r => {
      const mo = r.month_str?.slice(5,7);
      if (!mo || !r.Shop) return;
      if (!matrix[r.Shop]) matrix[r.Shop] = {};
      matrix[r.Shop][mo] = (matrix[r.Shop][mo] || 0) + r.Quantity;
    });
    const shops = Object.keys(matrix).sort();
    const months = Array.from({length:12},(_,i)=>String(i+1).padStart(2,"0"));
    // Flatten to rows per shop
    const rows = shops.map(shop => {
      const row = { shop };
      months.forEach((mo,i) => { row[monthNames[i]] = Math.round(matrix[shop][mo] || 0); });
      row.total = months.reduce((s,mo) => s + (matrix[shop][mo]||0), 0);
      return row;
    });
    const maxVal = Math.max(...rows.flatMap(r => Object.values(r).filter(v => typeof v === "number" && v > 0)));
    return { rows, months: monthNames, maxVal };
  }, [shopMonthly, allShopMonthly, currentYear]);

  // ── Consumption Analysis: monthly detail (per-shop stacked area) ──
  const consumptionMonthlyData = useMemo(() => {
    const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    // Use selected trendYears, aggregate all shops per month-year
    const byMonthYear = {};
    const sourceData = allShopMonthly.length ? allShopMonthly : shopMonthly;
    sourceData
      .filter(r => !trendYears.length || trendYears.includes(r.month_str?.slice(0,4)))
      .forEach(r => {
        const key = r.month_str;
        if (!key) return;
        if (!byMonthYear[key]) byMonthYear[key] = { monthStr: key };
        byMonthYear[key][r.Shop] = (byMonthYear[key][r.Shop] || 0) + r.Quantity;
        byMonthYear[key].total   = (byMonthYear[key].total   || 0) + r.Quantity;
      });
    return Object.values(byMonthYear)
      .sort((a,b) => a.monthStr.localeCompare(b.monthStr))
      .map(r => ({ ...r, label: formatXAxisDate(r.monthStr) }));
  }, [allShopMonthly, shopMonthly, trendYears]);

  // ── Consumption Analysis: day-of-week pattern (plant-wide) ──
  const consumptionDowData = useMemo(() => {
    const DOW = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
    const totals = Array(7).fill(0);
    const months = allShopMonthly.length ? allShopMonthly : shopMonthly;
    const filtered = trendYears.length
      ? months.filter(r => trendYears.includes(r.month_str?.slice(0,4)))
      : months;
    filtered.forEach(r => {
      const parts = r.month_str?.split("-");
      if (!parts || parts.length < 2) return;
      const yr = parseInt(parts[0], 10);
      const mo = parseInt(parts[1], 10);
      const daysInMonth = new Date(yr, mo, 0).getDate();
      const dailyAvg = r.Quantity / daysInMonth;
      for (let d = 1; d <= daysInMonth; d++) {
        const dow = new Date(yr, mo - 1, d).getDay();
        const idx = dow === 0 ? 6 : dow - 1;
        totals[idx] += dailyAvg;
      }
    });
    const totalMonths = filtered.length || 1;
    const today = new Date();
    const dowDates = Array(7).fill(null);
    for (let back = 0; back < 14; back++) {
      const d = new Date(today); d.setDate(today.getDate() - back);
      const dow = d.getDay();
      const idx = dow === 0 ? 6 : dow - 1;
      if (!dowDates[idx]) dowDates[idx] = String(d.getDate()).padStart(2,"0") + "/" + String(d.getMonth()+1).padStart(2,"0");
    }
    return DOW.map((day, i) => ({
      day,
      tickLabel: dowDates[i] ? day + " " + dowDates[i] : day,
      avg: Math.round(totals[i] / totalMonths),
    }));
  }, [allShopMonthly, shopMonthly, trendYears]);

  const maxConsumptionDowVal = useMemo(() => {
    if (!consumptionDowData.length) return 0;
    return Math.max(...consumptionDowData.map(x => x.avg || 0));
  }, [consumptionDowData]);

  const forecastExtended = useMemo(()=>{
    if(!history.length || !matDetail) return filteredHistory;
    const base = [...filteredHistory];
    const lastDate = history.filter(r=>r.year===currentYear).slice(-1)[0]?.date
                  || history[history.length-1]?.date || "";
    if(!lastDate) return base;
    const [yr, mo] = lastDate.split("-").map(Number);
    const monthlyForecasts = matDetail.forecast?.monthly_forecasts || [matDetail.forecast?.predicted_next_month || 0];
    monthlyForecasts.forEach((pred, i) => {
      let nm = mo + i + 1; let ny = yr;
      while(nm > 12){ nm -= 12; ny++; }
      base.push({ date:`${ny}-${String(nm).padStart(2,"0")}`, qty:null, forecast:Math.round(pred) });
    });
    return base;
  },[filteredHistory, history, matDetail, currentYear]);

  const activeYearHistory = useMemo(() => {
    return history.filter(r => r.year === currentYear);
  }, [history, currentYear]);

  const demandIntelligenceKPIs = useMemo(() => {
    const formatMonthName = (dateStr) => {
      if (!dateStr) return "—";
      const parts = dateStr.split("-");
      if (parts.length < 2) return dateStr;
      const yr = parts[0];
      const moIdx = parseInt(parts[1], 10) - 1;
      const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      return `${monthNames[moIdx] || parts[1]} ${yr}`;
    };
    if (!activeYearHistory.length) {
      return { currentMonth: 0, peakMonth: "—", lowestMonth: "—", forecastNext: 0 };
    }
    let peakQty = -Infinity;
    let peakRec = null;
    let lowestQty = Infinity;
    let lowestRec = null;
    activeYearHistory.forEach(r => {
      if (r.qty > peakQty) { peakQty = r.qty; peakRec = r; }
      if (r.qty < lowestQty) { lowestQty = r.qty; lowestRec = r; }
    });
    const currentRec = activeYearHistory[activeYearHistory.length - 1];
    return {
      currentMonth: currentRec?.qty || matDetail?.forecast?.current_month_consumption || 0,
      peakMonth: peakRec ? formatMonthName(peakRec.date) : "—",
      lowestMonth: lowestRec ? formatMonthName(lowestRec.date) : "—",
      forecastNext: matDetail?.forecast?.predicted_next_month || 0
    };
  }, [activeYearHistory, matDetail, currentYear]);

  const keyDates = useMemo(() => {
    const dates = { peak: "", lowest: "", current: "", forecastStart: "" };
    if (!activeYearHistory.length) return dates;
    let peakQty = -Infinity;
    let peakDate = "";
    let lowestQty = Infinity;
    let lowestDate = "";
    activeYearHistory.forEach(r => {
      if (r.qty > peakQty) { peakQty = r.qty; peakDate = r.date; }
      if (r.qty < lowestQty) { lowestQty = r.qty; lowestDate = r.date; }
    });
    dates.peak = peakDate;
    dates.lowest = lowestDate;
    dates.current = activeYearHistory[activeYearHistory.length - 1].date;
    const firstForecast = forecastExtended.find(r => r.qty === null || r.qty === undefined);
    if (firstForecast) dates.forecastStart = firstForecast.date;
    return dates;
  }, [activeYearHistory, forecastExtended]);

  const sameMachineMats = useMemo(()=>{
    if(!matDetail) return [];
    return procurement.filter(r=>r.machine===matDetail.machine && r.material!==matDetail.material && r.risk!=="Low").slice(0,5);
  },[procurement, matDetail]);

  const totalProcurementUnits = useMemo(() => {
    // Use consolidated data to prevent double-counting materials across shops
    return consolidatedProcurement.reduce((sum, c) => sum + c.total_order_qty, 0);
  }, [consolidatedProcurement]);

  const shopTrendMinMaxLatest = useMemo(() => {
    if (!shopTrendChartData.length) return { minIdx: -1, maxIdx: -1, latestIdx: -1 };
    let minVal = Infinity;
    let minIdx = -1;
    let maxVal = -Infinity;
    let maxIdx = -1;
    shopTrendChartData.forEach((d, idx) => {
      const val = d.Quantity;
      if (val < minVal) { minVal = val; minIdx = idx; }
      if (val > maxVal) { maxVal = val; maxIdx = idx; }
    });
    const latestIdx = shopTrendChartData.length - 1;
    return { minIdx, maxIdx, latestIdx };
  }, [shopTrendChartData]);

  const fallbackUsagePct = useMemo(() => {
    const fallbackCount = procurement.filter(r => r.developer?.fallback_used).length;
    const totalCount = procurement.length || 1;
    return ((fallbackCount / totalCount) * 100).toFixed(0);
  }, [procurement]);

  const highRisk      = alerts.filter(a=>a.risk==="High").length;
  const medRisk       = alerts.filter(a=>a.risk==="Medium").length;
  const totalMat      = plantSummary?.total_materials || procurement.length || 1;
  const uniqueLowRiskMats = new Set(procurement.filter(r=>r.risk==="Low").map(r=>r.material));
  const healthScore   = Math.round((uniqueLowRiskMats.size / totalMat)*100);
  const maxMat        = Math.max(...topMats.map(m=>Math.abs(m.total_quantity||0)));
  const totalAbcQty   = abcData.reduce((sum,d)=>sum+(d.total_qty||0),0) || 1;
  const activeYearMeta = yearMetadata[currentYear] || plantSummary?.year_metadata;
  const yearLabel = activeYearMeta?.is_ytd ? `${currentYear} YTD` : `${currentYear} Total`;

  const top3Urgent = useMemo(()=>{
    return [...procurement]
      .filter(r=>r.risk!=="Low")
      .sort((a,b)=>(a.lead_time?.days_to_runout??999)-(b.lead_time?.days_to_runout??999))
      .slice(0,3);
  },[procurement]);

  // Urgency config
  const urgCfg = {
    Critical:{ bg:"#fef2f2", border:"#fca5a5", text:T.red,    dot:"#ef4444" },
    Watch:   { bg:"#fffbeb", border:"#fcd34d", text:T.orange, dot:"#f59e0b" },
    OK:      { bg:"#f0fdf4", border:"#86efac", text:T.green,  dot:"#22c55e" },
  };


  // Top procurement KPI — units to order (same recommended_qty field)
  const topTotalUnits   = filteredProcurement.reduce((a,r)=>a+(r.order?.recommended_qty||0),0);

  // ── Year pill toggle helper ────────────────────────────
  const handleYearPill = (yr) => {
    setTrendYears(prev => {
      if(prev.includes(yr)) {
        // Deselect: keep at least one year
        return prev.length > 1 ? prev.filter(y=>y!==yr) : prev;
      } else {
        return [...prev, yr];
      }
    });
  };

  const handleAllYears = () => {
    const allSelected = allYearsAvailable.every(yr=>trendYears.includes(yr));
    if(allSelected) {
      // Deselect all → keep only selected dashboard year
      setTrendYears([currentYear]);
    } else {
      // Select all
      setTrendYears([...allYearsAvailable]);
    }
  };

  const allYearsSelected = allYearsAvailable.every(yr=>trendYears.includes(yr));

  if(loading) return (
    <div style={{ minHeight:"100vh", display:"flex", alignItems:"center", justifyContent:"center", background:T.gray50, fontFamily:"'Plus Jakarta Sans'" }}>
      <div style={{ textAlign:"center" }}>
        <div style={{ display:"inline-flex", alignItems:"center", gap:12, marginBottom:16 }}>
          <span style={{ fontSize:38, fontWeight:900, color:T.blue, letterSpacing:"-0.03em" }}>TATA</span>
          <span style={{ width:2, height:32, background:T.gray300 }} />
          <span style={{ fontSize:22, fontWeight:700, color:T.gray600, letterSpacing:"0.08em" }}>MOTORS</span>
        </div>
        <div style={{ display:"flex", alignItems:"center", justifyContent:"center", gap:8, color:T.gray500, fontSize:14 }}>
          <span className="loading-spinner" style={{ 
            width: 14, 
            height: 14, 
            border: `2px solid ${T.gray300}`, 
            borderTop: `2px solid ${T.blue}`, 
            borderRadius: "50%",
            display: "inline-block",
            animation: "spin 1s linear infinite"
          }} />
          <span>Loading...</span>
        </div>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    </div>
  );

  return (
    <div style={{ minHeight:"100vh", background:T.gray50, fontFamily:"'Plus Jakarta Sans', sans-serif", color:T.gray900 }}>
      <style>{FONTS}{`* { box-sizing:border-box; margin:0; padding:0; } select,input { appearance:none; } ::-webkit-scrollbar { width:5px; height:5px; } ::-webkit-scrollbar-thumb { background:${T.gray200}; border-radius:3px; }`}</style>

      {/* ── NAVBAR ── */}
      <nav style={{ background:T.blue, padding:"0 28px", height:54, display:"flex", alignItems:"center", justifyContent:"space-between", position:"sticky", top:0, zIndex:200, boxShadow:"0 2px 8px rgba(0,48,135,0.25)" }}>
        <div style={{ display:"flex", alignItems:"center", gap:12 }}>
          <div
            onClick={() => setTab("overview")}
            style={{
              background: "#fff",
              borderRadius: 6,
              padding: "4px 10px",
              display: "flex",
              alignItems: "center",
              gap: 6,
              cursor: "pointer",
              userSelect: "none",
              transition: "transform 0.1s ease",
            }}
            onMouseDown={(e) => { e.currentTarget.style.transform = "scale(0.96)"; }}
            onMouseUp={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.transform = "scale(1)"; }}
          >
            <span style={{ fontSize:15, fontWeight:900, color:T.blue, letterSpacing:"-0.03em" }}>TATA</span>
            <span style={{ width:1, height:14, background:T.gray200 }} />
            <span style={{ fontSize:10, fontWeight:700, color:T.gray600, letterSpacing:"0.05em" }}>MOTORS</span>
          </div>
          <span style={{ color:"rgba(255,255,255,0.3)" }}>|</span>
          <span style={{ color:"#fff", fontSize:13, fontWeight:600 }}>Spare Parts Inventory Intelligence</span>
        </div>
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          {years.length > 0 && (
            <Sel
              value={currentYear}
              onChange={(yr)=>{ setDataYear(yr); setTrendYears([yr]); setShopYear(yr); setAllShopMonthly([]); }}
              options={years.map(y=>{
                const meta = yearMetadata[y];
                const suffix = meta?.is_ytd ? "YTD" : "Total";
                return { value:y, label:`${y} ${suffix}` };
              })}
              style={{ background:"rgba(255,255,255,0.12)", border:"1px solid rgba(255,255,255,0.25)", color:"#fff" }}
            />
          )}
          {highRisk > 0 && (
            <span style={{ background:"#ef4444", color:"#fff", borderRadius:999, padding:"3px 12px", fontSize:11, fontWeight:700 }}>
              🚨 {highRisk} Critical
            </span>
          )}
          <span style={{ background:"rgba(255,255,255,0.1)", border:"1px solid rgba(255,255,255,0.2)", color:"#fff", borderRadius:999, padding:"3px 12px", fontSize:11, fontFamily:"'IBM Plex Mono'" }}>
            ● LIVE
          </span>
        </div>
      </nav>

      {/* ── TABS ── */}
      <div style={{ background:"#fff", borderBottom:`1px solid ${T.gray200}`, padding:"0 28px", display:"flex", gap:0, overflowX:"auto" }}>
        {[
          { id:"overview",    label:"Executive Overview"       },
          { id:"procurement", label:"Procurement Intelligence" },
          { id:"shop",        label:"Shop Analysis"            },
          { id:"consumption", label:"Consumption Analysis"     },
          { id:"material",    label:"Material Deep Dive"       },
          { id:"morning",     label:"☀ Morning Meeting"        },
          { id:"developer",   label:"Developer Mode"           },
        ].map(t=>(
          <button key={t.id} onClick={()=>setTab(t.id)} style={{
            border:"none", background:"none", cursor:"pointer",
            padding:"13px 16px", fontSize:12, fontWeight:600, whiteSpace:"nowrap",
            color: tab===t.id ? T.blue : T.gray400,
            borderBottom: tab===t.id ? `2px solid ${T.blue}` : "2px solid transparent",
            fontFamily:"'Plus Jakarta Sans'", transition:"all 0.15s",
          }}>{t.label}</button>
        ))}
      </div>

      <div style={{ padding:"20px 28px", maxWidth:1440, margin:"0 auto" }}>

        {/* ═══════════════════════════════
            TAB 1: OVERVIEW
        ═══════════════════════════════ */}
        {tab==="overview" && <>

          {highRisk > 0 && (
            <div style={{ background:"#fef2f2", border:`1px solid #fca5a5`, borderRadius:10, padding:"12px 18px", marginBottom:18, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
              <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                <span style={{ fontSize:18 }}>🚨</span>
                <div>
                  <div style={{ fontWeight:700, color:T.red, fontSize:13 }}>{highRisk} material{highRisk>1?"s":""} at critical stockout risk — Immediate action required</div>
                  <div style={{ fontSize:11, color:"#991b1b", marginTop:2 }}>{alerts.filter(a=>a.risk==="High").map(a=>a.material).join(", ")}</div>
                </div>
              </div>
              <button onClick={()=>setTab("procurement")} style={{ background:T.red, color:"#fff", border:"none", borderRadius:6, padding:"6px 14px", fontSize:11, fontWeight:700, cursor:"pointer" }}>View All →</button>
            </div>
          )}

          <Section>Plant Health Overview — {yearLabel}{activeYearMeta?.is_ytd ? ` (${activeYearMeta.months_available} months · ${activeYearMeta.coverage_pct}% coverage)` : ""}</Section>
          <div style={{ display:"grid", gridTemplateColumns:"1.2fr 1fr 1fr 1.3fr 1fr 1fr", gap:12, marginBottom:4 }}>
            <div style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:10, padding:"18px 20px", boxShadow:"0 1px 4px rgba(0,0,0,0.04)", display:"flex", flexDirection:"column", justifyContent:"space-between" }}>
              <div style={{ fontSize:10, fontWeight:700, letterSpacing:"0.1em", textTransform:"uppercase", color:T.gray400, marginBottom:10 }}>Plant Health Score</div>
              <div style={{ display:"flex", alignItems:"flex-end", gap:10 }}>
                <div style={{ fontSize:42, fontWeight:800, color: healthScore>=70?T.green:healthScore>=50?T.orange:T.red, lineHeight:1 }}>{healthScore}%</div>
              </div>
              <div style={{ marginTop:10 }}>
                <div style={{ height:6, background:T.gray100, borderRadius:3 }}>
                  <div style={{ width:`${healthScore}%`, height:"100%", background:healthScore>=70?T.green:healthScore>=50?T.orange:T.red, borderRadius:3, transition:"width 0.8s" }} />
                </div>
                <div style={{ fontSize:11, color:T.gray400, marginTop:5 }}>
                  {uniqueLowRiskMats.size} of {totalMat} materials healthy
                </div>
              </div>
            </div>

            {[
              { label:"Total Materials",    value:fmt(plantSummary?.total_materials), sub:"Active spare SKUs",       accent:T.blue   },
              { label:"Total Inventory",    value:fmt(plantSummary?.total_inventory), sub:"Units currently in stock", accent:"#0891b2"},
              { label:"Procurement Exposure", value:fmt(Math.round(totalProcurementUnits)), sub:"Actual shortage requiring procurement", accent:T.blue2  },
              { label:"🚨 Critical Alerts", value:highRisk,                            sub:"Immediate action needed",  accent:T.red    },
              { label:"⚠️ Watch List",      value:medRisk,                             sub:"Monitor closely",          accent:T.orange },
            ].map(k=>(
              <div key={k.label} style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderLeft:`4px solid ${k.accent}`, borderRadius:10, padding:"16px 16px", boxShadow:"0 1px 4px rgba(0,0,0,0.04)", display:"flex", flexDirection:"column", justifyContent:"space-between" }}>
                <div style={{ fontSize:10, fontWeight:700, letterSpacing:"0.1em", textTransform:"uppercase", color:T.gray400, marginBottom:8 }}>{k.label}</div>
                <div style={{ fontSize:26, fontWeight:800, color:T.gray900, lineHeight:1.1 }}>{k.value}</div>
                <div style={{ fontSize:11, color:T.gray400, marginTop:5 }}>{k.sub}</div>
              </div>
            ))}
          </div>

          <Section>Top Priority Actions for Today</Section>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14, marginBottom:4 }}>
            {top3Urgent.map((r,i)=>(
              <div key={r.material} style={{ background:"#fff", border:`2px solid ${r.risk==="High"?"#fca5a5":"#fcd34d"}`, borderRadius:10, padding:"16px 18px", cursor:"pointer" }}
                onClick={()=>{ setSelected(r.material); setTab("material"); }}>
                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:12 }}>
                  <div>
                    <div style={{ fontSize:10, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:4 }}>#{i+1} Priority</div>
                    <div style={{ fontSize:18, fontWeight:800, color:T.gray900, fontFamily:"'IBM Plex Mono'" }}>{r.material}</div>
                    <div style={{ fontSize:11, color:T.gray600, marginTop:3 }}>{r.shop} · {r.machine}</div>
                  </div>
                  <RiskBadge level={r.risk} />
                </div>
                <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:8, marginBottom:10 }}>
                  <div style={{ background:T.gray50, borderRadius:6, padding:"8px 10px" }}>
                    <div style={{ fontSize:9, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>Stock Runs Out</div>
                    <div style={{ fontSize:14, fontWeight:700, color:r.lead_time?.days_to_runout<30?T.red:T.gray900, fontFamily:"'IBM Plex Mono'" }}>{r.lead_time?.days_to_runout ?? "—"}d</div>
                  </div>
                  <div style={{ background:T.gray50, borderRadius:6, padding:"8px 10px" }}>
                    <div style={{ fontSize:9, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>Order Qty</div>
                    <div style={{ fontSize:14, fontWeight:700, color:T.blue, fontFamily:"'IBM Plex Mono'" }}>{fmt(r.order?.recommended_qty)}</div>
                  </div>
                </div>
                <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between" }}>
                  <VendorBadge valType={r.lead_time?.procurement?.includes("Import")?2:1} />
                  <div style={{ fontSize:11, fontWeight:700, color:r.lead_time?.already_late?T.red:T.orange }}>
                    {r.lead_time?.already_late ? "🚨 ORDER TODAY" : `Reorder by ${r.lead_time?.reorder_by}`}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <Section>Inventory Distribution — {yearLabel}</Section>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:14 }}>
            <Card>
              <CardTitle title="ABC Consumption Split" sub={`Units consumed by ABC class in ${currentYear}`} />
              <div style={{ display:"flex", flexDirection:"column", gap:10, marginBottom:14 }}>
                {abcData.map(d=>{
                  const pct = (d.total_qty / totalAbcQty * 100).toFixed(1);
                  const lakhUnits = (d.total_qty / 100000).toFixed(2);
                  return (
                    <div key={d.ABC_Class} style={{ display:"flex", alignItems:"center", gap:10 }}>
                      <span style={{ width:22, height:22, borderRadius:6, background:ABC_COLORS[d.ABC_Class]+"22", color:ABC_COLORS[d.ABC_Class], display:"flex", alignItems:"center", justifyContent:"center", fontSize:12, fontWeight:800, flexShrink:0 }}>{d.ABC_Class}</span>
                      <div style={{ flex:1 }}>
                        <div style={{ display:"flex", justifyContent:"space-between", marginBottom:3, fontSize:11 }}>
                          <span style={{ fontWeight:600, color:T.gray900 }}>{d.ABC_Class}-Class ({pct}%) | {lakhUnits} Lakh Units</span>
                          <span style={{ fontFamily:"'IBM Plex Mono'", color:T.gray600 }}>{fmt(d.total_qty)} units</span>
                        </div>
                        <div style={{ height:5, background:T.gray100, borderRadius:3 }}>
                          <div style={{ width:`${(d.total_qty/totalAbcQty)*100}%`, height:"100%", background:ABC_COLORS[d.ABC_Class], borderRadius:3 }} />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div style={{ position: "relative", height: 220, display: "flex", justifyContent: "center", alignItems: "center" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={abcData}
                      dataKey="total_qty"
                      nameKey="ABC_Class"
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={3}
                      label={({ name, percent }) => `${name}-Class: ${(percent * 100).toFixed(1)}%`}
                      labelLine={true}
                    >
                      {abcData.map((d,i)=><Cell key={i} fill={ABC_COLORS[d.ABC_Class]||T.blue} />)}
                    </Pie>
                    <Tooltip formatter={v=>[fmt(v),"Quantity Consumed"]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ position: "absolute", textAlign: "center", pointerEvents: "none" }}>
                  <div style={{ fontSize: 10, color: T.gray400, textTransform: "uppercase", fontWeight: 700 }}>Total Consumption</div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: T.gray900, lineHeight: 1.2, marginTop: 2 }}>{(totalAbcQty / 100000).toFixed(1)} Lakh Units</div>
                </div>
              </div>
            </Card>

            <Card>
              <CardTitle title={`Shop-Wise Consumption — ${currentYear}`} sub="Total units consumed per shop in selected year" />
              {shopDataCurrent.map((s,i)=>(
                <HBar key={s.Shop} rank={i+1} label={s.Shop} value={s.Quantity} max={maxShopCurrent} color={SHOP_COLORS[i%SHOP_COLORS.length]} />
              ))}
            </Card>

            <Card>
              <CardTitle title="Top 10 Materials" sub="By total consumption · Click to drill down" />
              {topMats.slice(0,10).map((m,i)=>(
                <HBar
                  key={m.Material}
                  rank={i+1}
                  label={m.Material}
                  value={m.total_quantity}
                  max={maxMat}
                  color={MAT_COLORS[i%MAT_COLORS.length]}
                  onClick={() => {
                    setSelected(m.Material);
                    setTab("material");
                  }}
                />
              ))}
            </Card>
          </div>
        </>}

        {/* ═══════════════════════════════
            TAB 2: PROCUREMENT INTELLIGENCE
        ═══════════════════════════════ */}
        {tab==="procurement" && <>
          <Section>Procurement Intelligence</Section>

          {/* ── View Toggle ── */}
          <div style={{ display:"flex", alignItems:"center", gap:0, marginBottom:14 }}>
            <div style={{ display:"inline-flex", background:T.gray100, borderRadius:8, padding:2, border:`1px solid ${T.gray200}` }}>
              {[
                { id:"shop", label:"🏭 Shop View", sub:"Operational" },
                { id:"consolidated", label:"📦 Consolidated View", sub:"Purchase Orders" },
              ].map(v=>(
                <button key={v.id}
                  onClick={()=>{ setProcurementView(v.id); setExpandedProcurementRows({}); }}
                  style={{
                    background: procurementView===v.id ? "#fff" : "transparent",
                    border: procurementView===v.id ? `1px solid ${T.gray200}` : "1px solid transparent",
                    borderRadius:7, padding:"8px 18px", cursor:"pointer",
                    boxShadow: procurementView===v.id ? "0 1px 4px rgba(0,0,0,0.08)" : "none",
                    transition:"all 0.2s",
                  }}>
                  <div style={{ fontSize:12, fontWeight:700, color: procurementView===v.id ? T.blue : T.gray600, whiteSpace:"nowrap" }}>{v.label}</div>
                  <div style={{ fontSize:9, color: procurementView===v.id ? T.blue2 : T.gray400, marginTop:1 }}>{v.sub}</div>
                </button>
              ))}
            </div>
            <div style={{ marginLeft:16, fontSize:11, color:T.gray400, borderLeft:`1px solid ${T.gray200}`, paddingLeft:14 }}>
              {procurementView==="shop" ? "Per-shop material rows for operational planning" : "Grouped by material for purchase order generation"}
            </div>
          </div>

          <div style={{ display:"flex", gap:10, marginBottom:14, flexWrap:"wrap", alignItems:"center" }}>
            <Sel value={riskFilter} onChange={setRiskFilter} options={[{value:"all",label:"All Risk Levels"},{value:"High",label:"🚨 High Risk"},{value:"Medium",label:"⚠️ Medium Risk"},{value:"Low",label:"✅ Low Risk"}]} />
            <Sel value={abcFilter}  onChange={setAbcFilter}  options={[{value:"all",label:"All ABC Classes"},{value:"A",label:"A-Class (Critical)"},{value:"B",label:"B-Class (Important)"},{value:"C",label:"C-Class (Normal)"}]} />
            <Sel value={shopFilter} onChange={setShopFilter} options={shops.map(s=>({value:s,label:s==="all"?"All Shops":s}))} />
            <MaterialSearch
              value={materialFilter === "all" ? "" : materialFilter}
              onChange={(m) => setMaterialFilter(m || "all")}
              materials={materials}
              placeholder="Search materials..."
              allowClear
            />
            <span style={{ marginLeft:"auto", fontSize:12, color:T.gray400 }}>
              {procurementView==="shop"
                ? `${filteredProcurement.length} of ${procurement.length} materials · sorted by urgency`
                : `${filteredConsolidated.length} of ${consolidatedProcurement.length} unique materials · consolidated`}
            </span>
          </div>

          {/* ── KPI Cards ── */}
          {procurementView==="shop" ? (
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:14 }}>
              {[
                { label:"Total Units to Order", value:fmt(topTotalUnits),                                               accent:T.blue  },
                { label:"High Risk",            value:filteredProcurement.filter(r=>r.risk==="High").length,            accent:T.red   },
                { label:"Medium Risk",          value:filteredProcurement.filter(r=>r.risk==="Medium").length,          accent:T.orange},
                { label:"Sufficient Stock",     value:filteredProcurement.filter(r=>r.risk==="Low").length,             accent:T.green },
              ].map(k=>(
                <div key={k.label} style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderLeft:`4px solid ${k.accent}`, borderRadius:10, padding:"12px 14px" }}>
                  <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color:T.gray400, marginBottom:5 }}>{k.label}</div>
                  <div style={{ fontSize:24, fontWeight:800, color:T.gray900 }}>{k.value}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:14 }}>
              {[
                { label:"Total Consolidated Order", value:fmt(filteredConsolidated.reduce((a,c)=>a+c.total_recommended_qty,0)), accent:T.blue  },
                { label:"High Risk Materials",      value:filteredConsolidated.filter(r=>r.highest_risk==="High").length,       accent:T.red   },
                { label:"Medium Risk Materials",    value:filteredConsolidated.filter(r=>r.highest_risk==="Medium").length,     accent:T.orange},
                { label:"Sufficient Stock",         value:filteredConsolidated.filter(r=>r.highest_risk==="Low").length,        accent:T.green },
              ].map(k=>(
                <div key={k.label} style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderLeft:`4px solid ${k.accent}`, borderRadius:10, padding:"12px 14px" }}>
                  <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color:T.gray400, marginBottom:5 }}>{k.label}</div>
                  <div style={{ fontSize:24, fontWeight:800, color:T.gray900 }}>{k.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* ── Shop View Table (existing) ── */}
          {procurementView==="shop" && (
          <Card p={0}>
            <div style={{ overflowX:"auto", maxHeight:540, overflowY:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                <thead style={{ position:"sticky", top:0, zIndex:10 }}>
                  <tr style={{ background:T.gray50 }}>
                    {["Material","Shop","Days Left","Current Stock","30D Forecast","60D Forecast","90D Forecast","Order Qty","Risk",""].map(h=>(
                      <th key={h} style={{ padding:"9px 11px", textAlign:"left", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.05em", borderBottom:`1px solid ${T.gray200}`, whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredProcurement.map((r,i)=>{
                    const daysLeft = r.lead_time?.days_to_runout ?? 999;
                    const isImport = r.lead_time?.procurement?.includes("Import");
                    const expanded = !!expandedProcurementRows[`${r.material}-${r.shop}`];
                    return (
                      <React.Fragment key={`${r.material}-${r.shop}`}>
                        <tr
                          style={{ borderBottom:`1px solid ${T.gray100}`, background: expanded ? T.gray100 : r.risk==="High"?"#fff8f8":r.risk==="Medium"?"#fffdf5":"#fff", cursor:"pointer" }}
                          onClick={() => {
                            setExpandedProcurementRows(prev => ({
                              ...prev,
                              [`${r.material}-${r.shop}`]: !prev[`${r.material}-${r.shop}`]
                            }));
                          }}>
                          <td style={{ padding:"10px 11px", fontWeight:700, color:T.blue, fontFamily:"'IBM Plex Mono'", fontSize:12 }}>{r.material}</td>
                          <td style={{ padding:"10px 11px", color:T.gray600, fontSize:11 }}>{r.shop}</td>
                          <td style={{ padding:"10px 11px" }}>
                            <span style={{ fontFamily:"'IBM Plex Mono'", fontWeight:700, fontSize:13, color:daysLeft<=30?T.red:daysLeft<=60?T.orange:T.green }}>
                              {daysLeft >= 999 ? "—" : `${daysLeft}d`}
                            </span>
                          </td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'", fontWeight:600 }}>{fmt(r.inventory?.current_stock)}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(r.forecast?.forecast_30d)}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(r.forecast?.forecast_60d)}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(r.forecast?.forecast_90d)}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'", fontWeight:700, color:T.blue }}>{fmt(r.order?.recommended_qty)}</td>
                          <td style={{ padding:"10px 11px" }}><RiskBadge level={r.risk} /></td>
                          <td style={{ padding:"10px 11px", textAlign:"center", color:T.gray400, fontSize:12 }}>{expanded ? "▲" : "▼"}</td>
                        </tr>
                        {expanded && (
                          <tr>
                            <td colSpan={10} style={{ background: T.gray50, padding: "14px 20px", borderBottom: `1px solid ${T.gray200}` }}>
                              {/* Aggregation calculations */}
                              {(() => {
                                const materialRows = procurement.filter(p => p.material === r.material);
                                const totalOrderQty = materialRows.reduce((sum, p) => sum + (p.order?.recommended_qty || 0), 0);
                                const shopSet = new Set(materialRows.map(p => p.shop));
                                const shopCount = shopSet.size;
                                return (
                                  <div style={{ marginBottom: 12 }}>
                                    <div style={{ fontSize: 12, color: T.gray600, marginBottom: 4 }}><strong>Total Order Qty Required:</strong> {fmt(totalOrderQty)}</div>
                                    <div style={{ fontSize: 12, color: T.gray600, marginBottom: 4 }}><strong>Total Shops Using This Material:</strong> {shopCount}</div>
                                    <div style={{ fontSize: 12, color: T.gray600 }}><strong>Shop-wise Order Requirements:</strong></div>
                                    <div style={{ marginTop: 4 }}>
                                      {Array.from(shopSet).map(shop => {
                                        const shopRow = materialRows.find(p => p.shop === shop);
                                        const qty = shopRow?.order?.recommended_qty ?? 0;
                                        return (
                                          <div key={shop} style={{ fontSize: 11, color: T.gray600 }}>
                                            {shop} → {fmt(qty)} units
                                          </div>
                                        );
                                      })}
                                    </div>
                                  </div>
                                );
                              })()}
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px 20px", marginBottom: 12 }}>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Machine:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900, fontFamily: "'IBM Plex Mono'" }}>{r.machine}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>ABC Class:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900, fontFamily: "'IBM Plex Mono'" }}>{r.abc_class}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Lead Time:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900 }}>{r.lead_time?.total}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Safety Stock:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900, fontFamily: "'IBM Plex Mono'" }}>{fmt(r.inventory?.safety_stock)}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Forecast Source:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900 }}>{r.forecast?.forecast_source || "AI Forecast Engine"}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Reorder Date:</span>{" "}
                                  <strong style={{ fontSize: 12, color: r.lead_time?.already_late ? T.red : T.gray900 }}>{r.lead_time?.reorder_by}</strong>
                                </div>
                              </div>
                              <div style={{ display: "flex", justifyContent: "flex-end", borderTop: `1px dashed ${T.gray200}`, paddingTop: 10 }}>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelected(r.material);
                                    setTab("material");
                                  }}
                                  style={{
                                    background: T.blue, color: "#fff", border: "none", borderRadius: 6,
                                    padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer",
                                    transition: "background 0.2s"
                                  }}
                                  onMouseEnter={e => e.currentTarget.style.background = T.blue2}
                                  onMouseLeave={e => e.currentTarget.style.background = T.blue}
                                >
                                  Analyze Deep Dive →
                                </button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          )}

          {/* ── Consolidated View Table (new) ── */}
          {procurementView==="consolidated" && (
          <Card p={0}>
            <div style={{ overflowX:"auto", maxHeight:540, overflowY:"auto" }}>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:12 }}>
                <thead style={{ position:"sticky", top:0, zIndex:10 }}>
                  <tr style={{ background:T.gray50 }}>
                    {["Material","Shops Requiring","Days Left","Current Stock","30D Forecast","60D Forecast","90D Forecast","Total Order Qty","Risk",""].map(h=>(
                      <th key={h} style={{ padding:"9px 11px", textAlign:"left", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.05em", borderBottom:`1px solid ${T.gray200}`, whiteSpace:"nowrap" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredConsolidated.map((c)=>{
                    const expanded = !!expandedProcurementRows[`consolidated-${c.material}`];
                    const daysLeft = c.min_days_left;
                    return (
                      <React.Fragment key={`consolidated-${c.material}`}>
                        <tr
                          style={{ borderBottom:`1px solid ${T.gray100}`, background: expanded ? T.gray100 : c.highest_risk==="High"?"#fff8f8":c.highest_risk==="Medium"?"#fffdf5":"#fff", cursor:"pointer" }}
                          onClick={() => {
                            setExpandedProcurementRows(prev => ({
                              ...prev,
                              [`consolidated-${c.material}`]: !prev[`consolidated-${c.material}`]
                            }));
                          }}>
                          <td style={{ padding:"10px 11px", fontWeight:700, color:T.blue, fontFamily:"'IBM Plex Mono'", fontSize:12 }}>{c.material}</td>
                          <td style={{ padding:"10px 11px", color:T.gray600, fontSize:11 }}>
                            <span style={{ background:"#eff6ff", color:T.blue2, borderRadius:999, padding:"2px 10px", fontSize:11, fontWeight:700, whiteSpace:"nowrap" }}>
                              {c.shops.length} {c.shops.length===1?"Shop":"Shops"}
                            </span>
                          </td>
                          <td style={{ padding:"10px 11px" }}>
                            <span style={{ fontFamily:"'IBM Plex Mono'", fontWeight:700, fontSize:13, color:daysLeft<=30?T.red:daysLeft<=60?T.orange:T.green }}>
                              {daysLeft >= 999 ? "—" : `${daysLeft}d`}
                            </span>
                          </td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'", fontWeight:600 }}>{fmt(Math.round(c.total_current_stock))}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(Math.round(c.total_30d))}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(Math.round(c.total_60d))}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'" }}>{fmt(Math.round(c.total_90d))}</td>
                          <td style={{ padding:"10px 11px", fontFamily:"'IBM Plex Mono'", fontWeight:700, color:T.blue }}>{fmt(Math.round(c.total_recommended_qty))}</td>
                          <td style={{ padding:"10px 11px" }}><RiskBadge level={c.highest_risk} /></td>
                          <td style={{ padding:"10px 11px", textAlign:"center", color:T.gray400, fontSize:12 }}>{expanded ? "▲" : "▼"}</td>
                        </tr>
                        {expanded && (
                          <tr>
                            <td colSpan={10} style={{ background: T.gray50, padding: "14px 20px", borderBottom: `1px solid ${T.gray200}` }}>
                              {/* ── Header ── */}
                              <div style={{ display:"flex", alignItems:"center", gap:12, marginBottom:14 }}>
                                <div style={{ fontSize:16, fontWeight:800, color:T.gray900, fontFamily:"'IBM Plex Mono'" }}>{c.material}</div>
                                <div style={{ fontSize:12, color:T.blue2, fontWeight:700 }}>Total Recommended Order: {fmt(Math.round(c.total_recommended_qty))} Units</div>
                              </div>

                              {/* ── Shop Breakdown ── */}
                              <div style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:8, padding:14, marginBottom:14 }}>
                                <div style={{ fontSize:12, fontWeight:700, color:T.gray900, marginBottom:10, borderBottom:`1px solid ${T.gray200}`, paddingBottom:6 }}>Shop Breakdown</div>
                                {c.rows.map(row=>(
                                  <div key={row.shop} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"6px 0", borderBottom:`1px dashed ${T.gray100}` }}>
                                    <span style={{ fontSize:12, color:T.gray600 }}>{row.shop}</span>
                                    <div style={{ display:"flex", alignItems:"center", gap:10 }}>
                                      <span style={{ fontSize:12, fontWeight:700, color:T.gray900, fontFamily:"'IBM Plex Mono'" }}>→ {fmt(row.order?.recommended_qty || 0)}</span>
                                      <RiskBadge level={row.risk} size={9} />
                                    </div>
                                  </div>
                                ))}
                                <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"8px 0 0", marginTop:4, borderTop:`2px solid ${T.gray200}` }}>
                                  <span style={{ fontSize:12, fontWeight:800, color:T.gray900 }}>Total</span>
                                  <span style={{ fontSize:13, fontWeight:800, color:T.blue, fontFamily:"'IBM Plex Mono'" }}>→ {fmt(Math.round(c.total_recommended_qty))}</span>
                                </div>
                              </div>

                              {/* ── Metadata Grid ── */}
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px 20px", marginBottom: 12 }}>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>ABC Class:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900, fontFamily: "'IBM Plex Mono'" }}>{c.abc_class}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Lead Time:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900 }}>{c.lead_time?.total}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Forecast Source:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900 }}>{c.forecast_source || "AI Forecast Engine"}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Safety Stock:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900, fontFamily: "'IBM Plex Mono'" }}>{fmt(Math.round(c.safety_stock))}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Reorder Date:</span>{" "}
                                  <strong style={{ fontSize: 12, color: T.gray900 }}>{c.reorder_by}</strong>
                                </div>
                                <div>
                                  <span style={{ fontSize: 11, color: T.gray400 }}>Min Days Left:</span>{" "}
                                  <strong style={{ fontSize: 12, fontFamily:"'IBM Plex Mono'", fontWeight:700, color:daysLeft<=30?T.red:daysLeft<=60?T.orange:T.green }}>{daysLeft >= 999 ? "—" : `${daysLeft}d`}</strong>
                                </div>
                              </div>
                              <div style={{ display: "flex", justifyContent: "flex-end", borderTop: `1px dashed ${T.gray200}`, paddingTop: 10 }}>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelected(c.material);
                                    setTab("material");
                                  }}
                                  style={{
                                    background: T.blue, color: "#fff", border: "none", borderRadius: 6,
                                    padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer",
                                    transition: "background 0.2s"
                                  }}
                                  onMouseEnter={e => e.currentTarget.style.background = T.blue2}
                                  onMouseLeave={e => e.currentTarget.style.background = T.blue}
                                >
                                  Analyze Deep Dive →
                                </button>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
          )}

          <div style={{ fontSize:11, color:T.gray400, marginTop:8, marginBottom:4 }}>
            {procurementView==="shop"
              ? "💡 Click any row to expand details or analyze material deep dive"
              : "📦 Consolidated view groups materials across shops — click to see shop-wise breakdown"}
          </div>
        </>}

        {/* ═══════════════════════════════
            TAB 3: SHOP ANALYSIS
        ═══════════════════════════════ */}
        {/* ═══════════════════════════════
            TAB 3: SHOP ANALYSIS
        ═══════════════════════════════ */}
        {tab==="shop" && <>
          {/* 1. Shop Summary Table (Appear ABOVE the selector) */}
          <Section>Shop Summary Overview — {yearLabel}</Section>
          <Card p={0} style={{ marginBottom: 18 }}>
            <div style={{ padding: "12px 16px", borderBottom: `1px solid ${T.gray100}` }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.gray900 }}>Shops Floor Consumption & Risk Overview</div>
              <div style={{ fontSize: 11, color: T.gray400, marginTop: 2 }}>High-level diagnostic summary of all shop floors in the active year</div>
            </div>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: T.gray50 }}>
                    {["Shop", "Total Consumption", "Critical Risks", "Medium Risks"].map(h => (
                      <th key={h} style={{ padding: "9px 16px", textAlign: "left", fontSize: 10, fontWeight: 700, color: T.gray400, textTransform: "uppercase", letterSpacing: "0.05em", borderBottom: `1px solid ${T.gray200}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {shopSummaryTableData.map((s, i) => (
                      <tr key={s.shop} style={{ borderBottom: `1px solid ${T.gray100}`, cursor: "pointer", background: selectedShop === s.shop ? T.gray50 : "#fff" }} onClick={() => setSelectedShop(s.shop)}>
                        <td style={{ padding: "9px 16px", fontWeight: 700, color: T.blue2, display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ width: 8, height: 8, borderRadius: "50%", background: SHOP_COLORS[i % SHOP_COLORS.length] }} />
                          {s.shop}
                        </td>
                        <td style={{ padding: "9px 16px", fontFamily: "'IBM Plex Mono'", fontWeight: 600 }}>{fmtDisplay(s.consumption)} units</td>
                        <td style={{ padding: "9px 16px", fontFamily: "'IBM Plex Mono'", fontWeight: 700, color: s.criticalRisks > 0 ? T.red : T.green }}>
                          {s.criticalRisks}
                        </td>
                        <td style={{ padding: "9px 16px", fontFamily: "'IBM Plex Mono'", fontWeight: 700, color: s.mediumRisks > 0 ? T.orange : T.green }}>
                          {s.mediumRisks}
                        </td>
                      </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* 2. Shop Selector Dropdown */}
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 18 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: T.gray600 }}>Drill-Down View:</span>
            <Sel
              value={selectedShop}
              onChange={setSelectedShop}
              options={[{ value: "all", label: "All Shops (Plant-Wide)" }, ...shopNames.map(s => ({ value: s, label: s }))]}
              style={{ minWidth: 220 }}
            />
          </div>

          {/* 3. Shop KPI Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 18 }}>
            {[
              {
                label: "Total Consumption",
                value: fmtDisplay(selectedShop === "all" ? shopData.reduce((sum, s) => sum + s.Quantity, 0) : (shopData.find(s => s.Shop === selectedShop)?.Quantity || 0)),
                sub: selectedShop === "all" ? `${yearLabel} plant-wide` : `${yearLabel} in ${selectedShop}`
              },
              {
                label: "Current Month Consumption",
                value: fmtDisplay(currentMonthConsumption),
                sub: `Latest month in ${currentYear}`
              },
              {
                label: "Peak Month",
                value: peakShopMonth,
                sub: `Highest demand month`
              },
              {
                label: "At-Risk Materials",
                value: shopAtRiskCount,
                sub: "Requires monitoring",
                color: shopAtRiskCount > 0 ? T.red : T.green
              }
            ].map(k => (
              <div key={k.label} style={{ background: "#fff", border: `1px solid ${T.gray200}`, borderRadius: 10, padding: "14px 16px", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
                <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: T.gray400, marginBottom: 5 }}>{k.label}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: k.color || T.gray900, fontFamily: "'IBM Plex Mono'", lineHeight: 1.1 }}>{k.value}</div>
                <div style={{ fontSize: 11, color: T.gray400, marginTop: 5 }}>{k.sub}</div>
              </div>
            ))}
          </div>

          {/* 4. Trend line chart */}
          <Card style={{ marginBottom: 18 }}>
            <CardTitle
              title={selectedShop === "all" ? "Plant-Wide Monthly Consumption Trend" : `${selectedShop} — Monthly Consumption Trend`}
              sub={`Selected year: ${currentYear} · Single line view for clean scaling`}
            />
            {shopTrendChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <LineChart data={shopTrendChartData} margin={{ top: 20, right: 55, left: 0, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                  <XAxis dataKey="month" tick={{ fill: T.gray400, fontSize: 10, fontFamily: "IBM Plex Mono" }} tickLine={false} axisLine={{ stroke: T.gray200 }} />
                  <YAxis tick={{ fill: T.gray400, fontSize: 10 }} tickLine={false} axisLine={false} width={50} />
                  <Tooltip content={<Tip />} />
                  <Line type="monotone" dataKey="Quantity" name="Consumption" stroke={T.blue} strokeWidth={3}
                    dot={{ r: 4, fill: T.blue }} activeDot={{ r: 6 }} connectNulls={true}>
                    <LabelList dataKey="Quantity" position="top" formatter={fmt} style={{ fill: T.gray600, fontSize: 9, fontFamily: "IBM Plex Mono", fontWeight: "bold" }} />
                  </Line>
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: T.gray400 }}>No trend data available</div>
            )}
          </Card>

          {/* ── Shop Filter Pills (Month-Wise & Day-Wise only) ── */}
          {true && (
            <div style={{ marginBottom:14 }}>
              <div style={{ display:"flex", alignItems:"center", gap:6, flexWrap:"wrap" }}>
                <span style={{ fontSize:12, fontWeight:700, color:T.gray600, marginRight:4 }}>Shops:</span>
                {/* All pill */}
                <button onClick={()=>setShopChartSel(new Set())} style={{
                  border:`1.5px solid ${shopChartSel.size===0 ? T.blue : T.gray200}`,
                  background: shopChartSel.size===0 ? T.blue : "#fff",
                  color: shopChartSel.size===0 ? "#fff" : T.gray600,
                  borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                  cursor:"pointer", transition:"all 0.15s",
                }}>All</button>
                {shopNames.map((s,i)=>{
                  const active = shopChartSel.has(s);
                  const color = SHOP_COLORS[i % SHOP_COLORS.length];
                  return (
                    <button key={s} onClick={()=>{
                      const next = new Set(shopChartSel);
                      active ? next.delete(s) : next.add(s);
                      setShopChartSel(next);
                    }} style={{
                      border:`1.5px solid ${active ? color : T.gray200}`,
                      background: active ? color+"22" : "#fff",
                      color: active ? color : T.gray600,
                      borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                      cursor:"pointer", transition:"all 0.15s",
                    }}>{s}</button>
                  );
                })}
              </div>
              {shopChartSel.size > 0 && (
                <div style={{ fontSize:11, color:T.gray400, marginTop:6 }}>
                  {shopChartSel.size} shop{shopChartSel.size>1?"s":""} selected · click a pill to deselect · click All to reset
                </div>
              )}
            </div>
          )}

          {/* ── View Toggle for Shop Analysis ── */}
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:16 }}>
            <span style={{ fontSize:12, fontWeight:700, color:T.gray600 }}>View:</span>
            {[
              { id:"monthly",    label:"📅 Month-Wise" },
              { id:"dayofweek",  label:"📆 Day-Wise"   },
            ].map(v=>(
              <button key={v.id} onClick={()=>setShopView(v.id)} style={{
                border:`1.5px solid ${shopView===v.id ? T.blue : T.gray200}`,
                background: shopView===v.id ? T.blue : "#fff",
                color: shopView===v.id ? "#fff" : T.gray600,
                borderRadius:6, padding:"6px 14px", fontSize:12, fontWeight:600,
                cursor:"pointer", transition:"all 0.15s",
              }}>{v.label}</button>
            ))}
          </div>

          {/* Month-Wise: grouped bar per shop (not stacked — avoids Press Shop domination) */}
          {shopView==="monthly" && (
            <Card style={{ marginBottom:18 }}>
              <CardTitle
                title="Month-Wise Consumption — Shop Breakdown"
                sub={`${shopChartSel.size===0?"All shops":shopChartActiveNames.join(", ")} · ${currentYear} · bars grouped by shop`}
              />
              {shopMonthlyBreakdownFiltered.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={shopMonthlyBreakdownFiltered} margin={{top:20,right:20,left:0,bottom:5}}
                    barCategoryGap="20%" barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                    <XAxis dataKey="month" tick={{fill:T.gray400,fontSize:10,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} />
                    <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={90} tickFormatter={v=>fmtK(v)} />
                    <Tooltip content={<Tip />} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{fontSize:11,paddingTop:8}} />
                    {shopChartActiveNames.map((s,i)=>(
                      <Bar
                        key={s}
                        dataKey={s}
                        name={s}
                        fill={SHOP_COLORS[i%SHOP_COLORS.length]}
                        radius={[3,3,0,0]}
                        maxBarSize={shopChartActiveNames.length > 4 ? 14 : 22}
                      >
                        <LabelList content={<AlwaysLabel threshold={maxShopBreakdownVal * 0.05} useShortFormat={true} />} />
                      </Bar>
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{height:300,display:"flex",alignItems:"center",justifyContent:"center",color:T.gray400}}>No data available</div>
              )}
            </Card>
          )}

          {/* Day-Wise: avg consumption by day of week with dates */}
          {shopView==="dayofweek" && (
            <Card style={{ marginBottom:18 }}>
              <CardTitle
                title="Day-of-Week Consumption Pattern"
                sub={`Average daily consumption by weekday · ${shopChartSel.size===0?"All Shops":shopChartActiveNames.join(", ")} · ${currentYear}`}
              />
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16}}>
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={shopDayOfWeekFiltered} margin={{top:20,right:20,left:0,bottom:28}}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                    <XAxis dataKey="tickLabel" tick={{fill:T.gray400,fontSize:9,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} angle={-20} textAnchor="end" interval={0} />
                    <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={52} />
                    <Tooltip content={<Tip />} formatter={(v,n,p)=>[fmtK(v),"Avg Daily"]} labelFormatter={l=>l} />
                    <Bar dataKey="avg" name="Avg Daily Consumption" radius={[4,4,0,0]}>
                      <LabelList content={<AlwaysLabel threshold={maxShopDayOfWeekVal * 0.05} useShortFormat={true} />} />
                      {shopDayOfWeekFiltered.map((d,i)=>(
                        <Cell key={i} fill={d.day==="Sat"||d.day==="Sun" ? T.orange : T.blue} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
                <div style={{display:"flex",flexDirection:"column",gap:8,justifyContent:"center"}}>
                  {shopDayOfWeekFiltered.map((d,i)=>{
                    const max = Math.max(...shopDayOfWeekFiltered.map(x=>x.avg));
                    const pct = max>0 ? (d.avg/max)*100 : 0;
                    const isWeekend = d.day==="Sat"||d.day==="Sun";
                    return (
                      <div key={d.day} style={{display:"flex",alignItems:"center",gap:8}}>
                        <span style={{width:80,fontSize:10,fontWeight:700,color:isWeekend?T.orange:T.blue,fontFamily:"'IBM Plex Mono'",whiteSpace:"nowrap"}}>{d.tickLabel}</span>
                        <div style={{flex:1,height:8,background:T.gray100,borderRadius:4}}>
                          <div style={{width:`${pct}%`,height:"100%",background:isWeekend?T.orange:T.blue,borderRadius:4,transition:"width 0.5s"}} />
                        </div>
                        <span style={{width:75,fontSize:11,textAlign:"right",fontFamily:"'IBM Plex Mono'",color:T.gray600}}>{fmt(d.avg)}</span>
                      </div>
                    );
                  })}
                  <div style={{marginTop:8,padding:"8px 12px",background:"#fffbeb",border:`1px solid #fcd34d`,borderRadius:6,fontSize:11,color:T.orange}}>
                    ⚠ Sat/Sun shown in orange — typically lower throughput
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Heatmap: shop × month grid */}
          {shopView==="heatmap" && (
            <Card style={{ marginBottom:18 }}>
              <CardTitle
                title="Consumption Heatmap — Shop × Month"
                sub={`Colour intensity = relative consumption · ${currentYear}`}
              />
              {shopHeatmapData.rows.length > 0 ? (
                <div style={{overflowX:"auto"}}>
                  <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                    <thead>
                      <tr>
                        <th style={{padding:"6px 10px",textAlign:"left",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`}}>Shop</th>
                        {shopHeatmapData.months.map(m=>(
                          <th key={m} style={{padding:"6px 6px",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`,textAlign:"center",minWidth:44}}>{m}</th>
                        ))}
                        <th style={{padding:"6px 10px",textAlign:"right",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`}}>Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {shopHeatmapData.rows.map((row,ri)=>(
                        <tr key={row.shop} style={{borderBottom:`1px solid ${T.gray100}`}}>
                          <td style={{padding:"8px 10px",fontWeight:700,color:T.blue2,whiteSpace:"nowrap"}}>{row.shop}</td>
                          {shopHeatmapData.months.map(m=>{
                            const val = row[m] || 0;
                            const intensity = shopHeatmapData.maxVal > 0 ? val/shopHeatmapData.maxVal : 0;
                            const bg = `rgba(0,48,135,${0.07+intensity*0.75})`;
                            const textColor = intensity > 0.55 ? "#fff" : T.gray900;
                            return (
                              <td key={m} style={{padding:"8px 6px",textAlign:"center",fontFamily:"'IBM Plex Mono'",fontSize:10,fontWeight:600,background:bg,color:textColor,transition:"background 0.2s"}}>
                                {val > 0 ? fmtK(val) : "—"}
                              </td>
                            );
                          })}
                          <td style={{padding:"8px 10px",textAlign:"right",fontFamily:"'IBM Plex Mono'",fontWeight:800,color:T.gray900}}>{fmtK(row.total)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div style={{marginTop:12,display:"flex",alignItems:"center",gap:6,fontSize:11,color:T.gray400}}>
                    <span>Low</span>
                    {[0.1,0.25,0.45,0.65,0.85].map(v=>(
                      <div key={v} style={{width:28,height:14,borderRadius:3,background:`rgba(0,48,135,${0.07+v*0.75})`}} />
                    ))}
                    <span>High</span>
                  </div>
                </div>
              ) : (
                <div style={{height:200,display:"flex",alignItems:"center",justifyContent:"center",color:T.gray400}}>No data available</div>
              )}
            </Card>
          )}

          {/* 5. Top Materials & Risk Tables */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.2fr", gap: 14, marginBottom: 4 }}>
            <Card p={16}>
              <CardTitle title="Top Materials Consumed" sub={`Top 10 parts by actual yearly sum in ${currentYear}`} />
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: T.gray50 }}>
                      {["Material", "Consumption", "Contribution"].map(h => (
                        <th key={h} style={{ padding: "7px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: T.gray400, textTransform: "uppercase" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {shopTopMaterials.length > 0 ? shopTopMaterials.map((m, i) => (
                      <tr key={m.material} style={{ borderBottom: `1px solid ${T.gray100}` }}>
                        <td style={{ padding: "7px 10px", fontWeight: 700, color: T.blue, fontFamily: "'IBM Plex Mono'" }}>{m.material}</td>
                        <td style={{ padding: "7px 10px", fontFamily: "'IBM Plex Mono'" }}>{fmt(m.consumption)} units</td>
                        <td style={{ padding: "7px 10px", fontFamily: "'IBM Plex Mono'", color: T.gray600 }}>{m.pct.toFixed(1)}%</td>
                      </tr>
                    )) : (
                      <tr><td colSpan={3} style={{ padding: 20, textAlign: "center", color: T.gray400 }}>No materials found</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card p={16}>
              <CardTitle title="At-Risk Materials" sub="Active stockout alerts requiring attention" />
              <div style={{ overflowX: "auto", maxHeight: 310, overflowY: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                  <thead>
                    <tr style={{ background: T.gray50, position: "sticky", top: 0, zIndex: 1 }}>
                      {["Material", "Days Left", "Risk", "Order Needed"].map(h => (
                        <th key={h} style={{ padding: "7px 10px", textAlign: "left", fontSize: 10, fontWeight: 700, color: T.gray400, textTransform: "uppercase", borderBottom: `1px solid ${T.gray200}` }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {shopAtRiskList.length > 0 ? shopAtRiskList.map((m, i) => (
                      <tr key={m.material} style={{ borderBottom: `1px solid ${T.gray100}`, background: m.risk === "High" ? "#fff8f8" : "#fffdf5" }}>
                        <td style={{ padding: "7px 10px", fontWeight: 700, color: T.blue, fontFamily: "'IBM Plex Mono'" }}>{m.material}</td>
                        <td style={{ padding: "7px 10px", fontFamily: "'IBM Plex Mono'", fontWeight: 700, color: m.daysLeft <= 30 ? T.red : T.orange }}>{m.daysLeft}d</td>
                        <td style={{ padding: "7px 10px" }}><RiskBadge level={m.risk} size={10} /></td>
                        <td style={{ padding: "7px 10px", fontFamily: "'IBM Plex Mono'", fontWeight: 700, color: T.blue2 }}>{m.orderNeeded > 0 ? fmt(m.orderNeeded) : "—"}</td>
                      </tr>
                    )) : (
                      <tr><td colSpan={4} style={{ padding: 20, textAlign: "center", color: T.gray400 }}>All materials sufficient (Low Risk)</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>}

        {/* ═══════════════════════════════
            TAB 4: CONSUMPTION ANALYSIS
        ═══════════════════════════════ */}
        {tab==="consumption" && <>
          <Section>Plant-Wide Consumption Analysis</Section>

          {/* ── View Toggle ── */}
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:16 }}>
            <span style={{ fontSize:12, fontWeight:700, color:T.gray600 }}>View:</span>
            {[
              { id:"yoy",       label:"📊 Year-on-Year" },
              { id:"monthly",   label:"📅 Month-Wise"   },
              { id:"dayofweek", label:"📆 Day-Wise"     },
            ].map(v=>(
              <button key={v.id} onClick={()=>setConsumptionView(v.id)} style={{
                border:`1.5px solid ${consumptionView===v.id ? T.blue : T.gray200}`,
                background: consumptionView===v.id ? T.blue : "#fff",
                color: consumptionView===v.id ? "#fff" : T.gray600,
                borderRadius:6, padding:"6px 14px", fontSize:12, fontWeight:600,
                cursor:"pointer", transition:"all 0.15s",
              }}>{v.label}</button>
            ))}
          </div>
          {consumptionView==="yoy" && <>
            <Card style={{ marginBottom:16 }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:14 }}>
              <div>
                <div style={{ fontSize:13, fontWeight:700, color:T.gray900 }}>Year-on-Year Consumption Comparison</div>
                <div style={{ fontSize:11, color:T.gray400, marginTop:2 }}>Select years to compare · Seasonal and ABC charts below update too</div>
              </div>
              {/* Year pills with smart All toggle */}
              <div style={{ display:"flex", flexWrap:"wrap", gap:6, justifyContent:"flex-end", maxWidth:520 }}>
                {allYearsAvailable.map(yr=>{
                  const idx    = allYearsAvailable.indexOf(yr);
                  const active = trendYears.includes(yr);
                  const color  = MAT_COLORS[idx % MAT_COLORS.length];
                  return (
                    <button key={yr} onClick={()=>handleYearPill(yr)} style={{
                      border:`2px solid ${active ? color : T.gray200}`,
                      background: active ? color+"22" : T.gray50,
                      color:  active ? color : T.gray400,
                      borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                      cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                    }}>{yr}</button>
                  );
                })}
                {/* Smart All toggle */}
                <button onClick={handleAllYears} style={{
                  border:`2px solid ${allYearsSelected ? T.blue : T.gray200}`,
                  background: allYearsSelected ? T.blue+"22" : T.gray50,
                  color: allYearsSelected ? T.blue : T.gray400,
                  borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                  cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                  display:"flex", alignItems:"center", gap:5,
                }}>
                  {allYearsSelected ? "✕ Deselect All" : "Select All"}
                </button>
              </div>
            </div>

            {/* Selected years summary */}
            <div style={{ display:"flex", gap:8, marginBottom:12, fontSize:11, color:T.gray600, alignItems:"center" }}>
              <span style={{ color:T.gray400 }}>Showing:</span>
              {trendYears.sort().map(yr=>{
                const idx   = allYearsAvailable.indexOf(yr);
                const color = MAT_COLORS[idx % MAT_COLORS.length];
                return <span key={yr} style={{ background:color+"22", color, borderRadius:4, padding:"2px 8px", fontWeight:700, fontFamily:"'IBM Plex Mono'" }}>{yr}</span>;
              })}
            </div>

            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={yoyData} margin={{top:24,right:20,left:0,bottom:5}}>
                <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                <XAxis dataKey="month" tick={{fill:T.gray400,fontSize:11,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} />
                <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={55} />
                <Tooltip content={<Tip />} />
                <Legend iconType="circle" iconSize={8} wrapperStyle={{fontSize:11,paddingTop:10}} />
                {yoyYears.map((yr,i)=>(
                  <Bar key={yr} dataKey={yr} name={yr}
                    fill={MAT_COLORS[allYearsAvailable.indexOf(yr) % MAT_COLORS.length]}
                    radius={[3,3,0,0]} barSize={trendYears.length > 3 ? 10 : 16}>
                    <LabelList content={<AlwaysLabel threshold={maxYoyVal * 0.05} useShortFormat={true} />} />
                  </Bar>
                ))}
              </BarChart>
            </ResponsiveContainer>
          </Card>

          {/* Seasonal + ABC — both react to year selection */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginBottom:16 }}>
            <Card>
              <CardTitle
                title="Monthly Demand Trend"
                sub={`Monthly avg for selected years: ${trendYears.sort().join(", ")}`}
              />
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={seasonalData} margin={{top:24,right:10,left:0,bottom:5}}>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                  <XAxis dataKey="month" tick={{fill:T.gray400,fontSize:10,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} />
                  <YAxis tick={{fill:T.gray400,fontSize:9}} tickLine={false} axisLine={false} width={48} />
                  <Tooltip content={<Tip />} />
                  <Bar dataKey="avg" name="Avg Consumption" radius={[3,3,0,0]}>
                    <LabelList content={<AlwaysLabel threshold={maxSeasonalVal * 0.05} useShortFormat={true} />} />
                    {seasonalData.map((d,i)=>(
                      <Cell key={i} fill={`rgba(0,48,135,${0.2+d.intensity*0.8})`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>

            <Card>
              <CardTitle title="Demand By Material Criticality" sub={`Units consumed by criticality class in ${currentYear}`} />
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={abcDataFiltered} margin={{top:24,right:10,left:0,bottom:5}}>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                  <XAxis dataKey="ABC_Class" tick={{fill:T.gray400,fontSize:12}} tickLine={false} axisLine={false} />
                  <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={50} />
                  <Tooltip content={<Tip />} />
                  <Bar dataKey="total_qty" name="Quantity Consumed" radius={[4,4,0,0]}>
                    <LabelList content={<AlwaysLabel threshold={maxAbcVal * 0.05} useShortFormat={true} />} />
                    {abcDataFiltered.map((d,i)=><Cell key={i} fill={ABC_COLORS[d.ABC_Class]||T.blue} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div style={{ marginTop:10, display:"flex", flexDirection:"column", gap:5 }}>
                {abcDataFiltered.map(d=>(
                  <div key={d.ABC_Class} style={{ display:"flex", justifyContent:"space-between", fontSize:12, padding:"5px 10px", background:T.gray50, borderRadius:6 }}>
                    <span style={{ fontWeight:600, color:ABC_COLORS[d.ABC_Class] }}>
                      {d.ABC_Class === "A" ? "A = Critical Materials" : d.ABC_Class === "B" ? "B = Important Materials" : "C = Routine Materials"}
                    </span>
                    <span style={{ fontFamily:"'IBM Plex Mono'", color:T.gray600 }}>{fmt(d.total_qty)} units ({((d.total_qty / totalAbcQty) * 100).toFixed(1)}%)</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <Card>
            <CardTitle title="Highest Demand Materials" sub={`Selected-year ranking from API: ${currentYear}`} />
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={topMats.slice(0,10)} layout="vertical" margin={{top:5,right:75,left:10,bottom:5}}>
                <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} horizontal={false} />
                <XAxis type="number" tick={{fill:T.gray400,fontSize:9}} tickLine={false} axisLine={false} />
                <YAxis dataKey="Material" type="category" tick={{fill:T.gray600,fontSize:10,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} width={60} />
                <Tooltip content={<Tip />} />
                <Bar dataKey="total_quantity" name="Total Qty" radius={[0,3,3,0]} barSize={14}>
                  <LabelList position="right" style={{fill:T.gray600,fontSize:9,fontFamily:"IBM Plex Mono"}} formatter={v=>{
                    const totalPlant = plantSummary?.total_consumed || 1;
                    const pct = (Math.abs(v) / totalPlant) * 100;
                    return `${fmtK(v)} (${pct.toFixed(0)}%)`;
                  }} />
                  {topMats.slice(0,10).map((_,i)=><Cell key={i} fill={MAT_COLORS[i%MAT_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div style={{ marginTop:12, display:"grid", gridTemplateColumns:"1fr 1fr", gap:10 }}>
              {topMats.slice(0, 10).map((m, i) => {
                const qty = m.total_quantity || 0;
                const totalPlant = plantSummary?.total_consumed || 1;
                const pct = (qty / totalPlant) * 100;
                return (
                  <div key={m.Material} style={{ display:"flex", justifyContent:"space-between", fontSize:11, padding:"6px 10px", background:T.gray50, borderRadius:6, fontFamily:"'IBM Plex Mono'" }}>
                    <span style={{ fontWeight:600, color:T.blue }}>{i+1}. {m.Material}</span>
                    <span style={{ color:T.gray600 }}>{fmt(qty)} units · {pct.toFixed(1)}% of total demand</span>
                  </div>
                );
              })}
            </div>
          </Card>
          </>}

          {/* ── Month-Wise View ── */}
          {consumptionView==="monthly" && <>
            <Card style={{ marginBottom:16 }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:14 }}>
                <div>
                  <div style={{ fontSize:13, fontWeight:700, color:T.gray900 }}>Month-Wise Consumption Heatmap — Shop × Month</div>
                  <div style={{ fontSize:11, color:T.gray400, marginTop:2 }}>Colour intensity = relative consumption · Selected years: {trendYears.join(", ")}</div>
                </div>
                <div style={{ display:"flex", flexWrap:"wrap", gap:6, justifyContent:"flex-end", maxWidth:520 }}>
                  {allYearsAvailable.map(yr=>{
                    const idx = allYearsAvailable.indexOf(yr);
                    const active = trendYears.includes(yr);
                    const color = MAT_COLORS[idx % MAT_COLORS.length];
                    return (
                      <button key={yr} onClick={()=>handleYearPill(yr)} style={{
                        border:`2px solid ${active ? color : T.gray200}`,
                        background: active ? color+"22" : T.gray50,
                        color: active ? color : T.gray400,
                        borderRadius:999, padding:"3px 12px", fontSize:11, fontWeight:700,
                        cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                      }}>{yr}</button>
                    );
                  })}
                  {/* Select All toggle */}
                  <button onClick={handleAllYears} style={{
                    border:`2px solid ${allYearsSelected ? T.blue : T.gray200}`,
                    background: allYearsSelected ? T.blue+"22" : T.gray50,
                    color: allYearsSelected ? T.blue : T.gray400,
                    borderRadius:999, padding:"3px 12px", fontSize:11, fontWeight:700,
                    cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                    display:"flex", alignItems:"center", gap:5,
                  }}>
                    {allYearsSelected ? "✕ Deselect All" : "Select All"}
                  </button>
                </div>
              </div>
              {(() => {
                // Build heatmap from consumptionMonthlyData (which already respects trendYears)
                const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                const matrix = {};
                const sourceData = allShopMonthly.length ? allShopMonthly : shopMonthly;
                sourceData
                  .filter(r => !trendYears.length || trendYears.includes(r.month_str?.slice(0,4)))
                  .forEach(r => {
                    const mo = r.month_str?.slice(5,7);
                    if (!mo || !r.Shop) return;
                    if (!matrix[r.Shop]) matrix[r.Shop] = {};
                    matrix[r.Shop][mo] = (matrix[r.Shop][mo] || 0) + r.Quantity;
                  });
                const shops = Object.keys(matrix).sort();
                const months = Array.from({length:12},(_,i)=>String(i+1).padStart(2,"0"));
                const rows = shops.map(shop => {
                  const row = { shop };
                  months.forEach((mo,i) => { row[monthNames[i]] = Math.round(matrix[shop][mo] || 0); });
                  row.total = months.reduce((s,mo) => s + (matrix[shop][mo]||0), 0);
                  return row;
                });
                // Column totals
                const colTotals = {};
                monthNames.forEach(m => {
                  colTotals[m] = rows.reduce((s,r) => s+(r[m]||0), 0);
                });
                colTotals.total = rows.reduce((s,r) => s+r.total, 0);
                const maxVal = Math.max(...rows.flatMap(r => Object.values(r).filter(v => typeof v === "number" && v > 0)), 1);
                if (!rows.length) return <div style={{height:200,display:"flex",alignItems:"center",justifyContent:"center",color:T.gray400}}>No monthly data for selected years</div>;
                return (
                  <div style={{overflowX:"auto"}}>
                    <table style={{width:"100%",borderCollapse:"collapse",fontSize:11}}>
                      <thead>
                        <tr>
                          <th style={{padding:"6px 10px",textAlign:"left",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`,whiteSpace:"nowrap"}}>Shop</th>
                          {monthNames.map(m=>(
                            <th key={m} style={{padding:"6px 6px",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`,textAlign:"center",minWidth:48}}>{m}</th>
                          ))}
                          <th style={{padding:"6px 10px",textAlign:"right",fontSize:10,color:T.gray400,fontWeight:700,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`}}>Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map(row=>(
                          <tr key={row.shop} style={{borderBottom:`1px solid ${T.gray100}`}}>
                            <td style={{padding:"8px 10px",fontWeight:700,color:T.blue2,whiteSpace:"nowrap"}}>{row.shop}</td>
                            {monthNames.map(m=>{
                              const val = row[m] || 0;
                              const intensity = maxVal > 0 ? val/maxVal : 0;
                              const bg = `rgba(0,48,135,${0.07+intensity*0.75})`;
                              const textColor = intensity > 0.55 ? "#fff" : T.gray900;
                              return (
                                <td key={m} style={{padding:"8px 6px",textAlign:"center",fontFamily:"'IBM Plex Mono'",fontSize:10,fontWeight:600,background:bg,color:textColor,transition:"background 0.2s"}}>
                                  {val > 0 ? fmt(val) : "—"}
                                </td>
                              );
                            })}
                            <td style={{padding:"8px 10px",textAlign:"right",fontFamily:"'IBM Plex Mono'",fontWeight:800,color:T.gray900}}>{fmt(Math.round(row.total))}</td>
                          </tr>
                        ))}
                        {/* Totals row */}
                        <tr style={{borderTop:`2px solid ${T.gray200}`,background:T.gray50}}>
                          <td style={{padding:"8px 10px",fontWeight:800,color:T.gray900,fontSize:11}}>Total</td>
                          {monthNames.map(m=>(
                            <td key={m} style={{padding:"8px 6px",textAlign:"center",fontFamily:"'IBM Plex Mono'",fontSize:10,fontWeight:700,color:T.blue2}}>
                              {colTotals[m] > 0 ? fmt(Math.round(colTotals[m])) : "—"}
                            </td>
                          ))}
                          <td style={{padding:"8px 10px",textAlign:"right",fontFamily:"'IBM Plex Mono'",fontWeight:800,color:T.blue}}>{fmt(Math.round(colTotals.total))}</td>
                        </tr>
                      </tbody>
                    </table>
                    <div style={{marginTop:12,display:"flex",alignItems:"center",gap:6,fontSize:11,color:T.gray400}}>
                      <span>Low</span>
                      {[0.1,0.25,0.45,0.65,0.85].map(v=>(
                        <div key={v} style={{width:28,height:14,borderRadius:3,background:`rgba(0,48,135,${0.07+v*0.75})`}} />
                      ))}
                      <span>High</span>
                    </div>
                  </div>
                );
              })()}
            </Card>

            {/* Monthly Summary Table */}
            <Card style={{ marginBottom:16 }}>
              <CardTitle title="Monthly Consumption Summary" sub="Total plant-wide units consumed per month" />
              <div style={{ overflowX:"auto" }}>
                <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                  <thead>
                    <tr style={{background:T.gray50}}>
                      {["Month","Total Consumption","MoM Change","vs Avg"].map(h=>(
                        <th key={h} style={{padding:"8px 12px",textAlign:"left",fontSize:10,fontWeight:700,color:T.gray400,textTransform:"uppercase",borderBottom:`1px solid ${T.gray200}`}}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {consumptionMonthlyData.map((row, i) => {
                      const prev = i > 0 ? consumptionMonthlyData[i-1].total || 0 : null;
                      const mom = prev != null && prev > 0 ? ((row.total - prev) / prev) * 100 : null;
                      const avgTotal = consumptionMonthlyData.reduce((s,r)=>s+(r.total||0),0) / (consumptionMonthlyData.length||1);
                      const vsAvg = avgTotal > 0 ? ((row.total - avgTotal) / avgTotal) * 100 : null;
                      return (
                        <tr key={row.monthStr} style={{borderBottom:`1px solid ${T.gray100}`}}>
                          <td style={{padding:"7px 12px",fontFamily:"'IBM Plex Mono'",fontWeight:700,color:T.gray900}}>{row.label}</td>
                          <td style={{padding:"7px 12px",fontFamily:"'IBM Plex Mono'",fontWeight:700,color:T.blue}}>{fmt(Math.round(row.total||0))}</td>
                          <td style={{padding:"7px 12px"}}>
                            {mom != null ? (
                              <span style={{fontSize:11,fontWeight:700,color:mom>=0?T.red:T.green,background:mom>=0?"#fef2f2":"#f0fdf4",borderRadius:999,padding:"2px 8px"}}>
                                {mom>=0?"▲":"▼"} {Math.abs(mom).toFixed(1)}%
                              </span>
                            ) : "—"}
                          </td>
                          <td style={{padding:"7px 12px"}}>
                            {vsAvg != null ? (
                              <span style={{fontSize:11,fontWeight:700,color:vsAvg>=0?T.orange:T.green,fontFamily:"'IBM Plex Mono'"}}>
                                {vsAvg>=0?"+":""}{vsAvg.toFixed(1)}%
                              </span>
                            ) : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Card>
          </>}

          {/* ── Day-Wise View ── */}
          {consumptionView==="dayofweek" && <>
            {/* Year selector pills */}
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
              <div style={{ fontSize:12, fontWeight:700, color:T.gray600 }}>Filter by Year:</div>
              <div style={{ display:"flex", flexWrap:"wrap", gap:6, justifyContent:"flex-end", maxWidth:520 }}>
                {allYearsAvailable.map(yr=>{
                  const idx = allYearsAvailable.indexOf(yr);
                  const active = trendYears.includes(yr);
                  const color = MAT_COLORS[idx % MAT_COLORS.length];
                  return (
                    <button key={yr} onClick={()=>handleYearPill(yr)} style={{
                      border:`2px solid ${active ? color : T.gray200}`,
                      background: active ? color+"22" : T.gray50,
                      color: active ? color : T.gray400,
                      borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                      cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                    }}>{yr}</button>
                  );
                })}
                <button onClick={handleAllYears} style={{
                  border:`2px solid ${allYearsSelected ? T.blue : T.gray200}`,
                  background: allYearsSelected ? T.blue+"22" : T.gray50,
                  color: allYearsSelected ? T.blue : T.gray400,
                  borderRadius:999, padding:"4px 14px", fontSize:11, fontWeight:700,
                  cursor:"pointer", fontFamily:"'IBM Plex Mono'", transition:"all 0.15s",
                  display:"flex", alignItems:"center", gap:5,
                }}>
                  {allYearsSelected ? "✕ Deselect All" : "Select All"}
                </button>
              </div>
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:14, marginBottom:16 }}>
              <Card>
                <CardTitle
                  title="Day-of-Week Consumption Pattern"
                  sub={`Avg daily consumption by weekday · plant-wide · years: ${trendYears.join(", ")}`}
                />
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={consumptionDowData} margin={{top:24,right:10,left:0,bottom:28}}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                    <XAxis dataKey="tickLabel" tick={{fill:T.gray400,fontSize:9,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} angle={-20} textAnchor="end" interval={0} />
                    <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={52} />
                    <Tooltip content={<Tip />} />
                    <Bar dataKey="avg" name="Avg Daily Consumption" radius={[4,4,0,0]}>
                      <LabelList content={<AlwaysLabel threshold={maxConsumptionDowVal * 0.05} useShortFormat={true} />} />
                      {consumptionDowData.map((d,i)=>(
                        <Cell key={i} fill={d.day==="Sat"||d.day==="Sun" ? T.orange : T.blue} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <Card>
                <CardTitle title="Day-Wise Breakdown" sub="Relative demand intensity by day of week" />
                <div style={{display:"flex",flexDirection:"column",gap:10,marginTop:8}}>
                  {consumptionDowData.map(d=>{
                    const max = Math.max(...consumptionDowData.map(x=>x.avg));
                    const pct = max > 0 ? (d.avg/max)*100 : 0;
                    const isWeekend = d.day==="Sat"||d.day==="Sun";
                    return (
                      <div key={d.day} style={{display:"flex",alignItems:"center",gap:10}}>
                        <span style={{width:80,fontSize:10,fontWeight:700,color:isWeekend?T.orange:T.blue,fontFamily:"'IBM Plex Mono'",whiteSpace:"nowrap"}}>{d.tickLabel||d.day}</span>
                        <div style={{flex:1,height:10,background:T.gray100,borderRadius:5}}>
                          <div style={{width:`${pct}%`,height:"100%",background:isWeekend?T.orange:T.blue,borderRadius:5,transition:"width 0.5s"}} />
                        </div>
                        <span style={{width:80,fontSize:11,textAlign:"right",fontFamily:"'IBM Plex Mono'",color:T.gray600}}>{fmt(d.avg)} / day</span>
                        <span style={{width:36,fontSize:10,textAlign:"right",color:T.gray400}}>{pct.toFixed(0)}%</span>
                      </div>
                    );
                  })}
                </div>
                <div style={{marginTop:14,display:"grid",gridTemplateColumns:"1fr 1fr",gap:10}}>
                  {[
                    { label:"Busiest Day", value: consumptionDowData.reduce((a,b)=>a.avg>b.avg?a:b,{day:"—",avg:0}).day, color:T.blue },
                    { label:"Quietest Day", value: consumptionDowData.filter(d=>d.avg>0).reduce((a,b)=>a.avg<b.avg?a:b,{day:"—",avg:Infinity}).day, color:T.green },
                    { label:"Weekday Avg", value: fmt(Math.round(consumptionDowData.slice(0,5).reduce((s,d)=>s+d.avg,0)/5)), color:T.blue2 },
                    { label:"Weekend Avg", value: fmt(Math.round(consumptionDowData.slice(5).reduce((s,d)=>s+d.avg,0)/2)), color:T.orange },
                  ].map(k=>(
                    <div key={k.label} style={{background:T.gray50,border:`1px solid ${T.gray200}`,borderRadius:8,padding:"10px 14px"}}>
                      <div style={{fontSize:10,fontWeight:700,textTransform:"uppercase",color:T.gray400,marginBottom:4}}>{k.label}</div>
                      <div style={{fontSize:18,fontWeight:800,color:k.color,fontFamily:"'IBM Plex Mono'"}}>{k.value}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>

            {/* Radar-style comparison using recharts AreaChart in circular form via ComposedChart */}
            <Card style={{ marginBottom:16 }}>
              <CardTitle
                title="Weekly Pattern — Line View"
                sub="Smoothed demand curve across the week · helps identify peak operational days"
              />
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={consumptionDowData} margin={{top:20,right:20,left:0,bottom:5}}>
                  <defs>
                    <linearGradient id="dowGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={T.blue} stopOpacity={0.25}/>
                      <stop offset="95%" stopColor={T.blue} stopOpacity={0.03}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                  <XAxis dataKey="tickLabel" tick={{fill:T.gray400,fontSize:9,fontFamily:"IBM Plex Mono"}} tickLine={false} axisLine={false} angle={-20} textAnchor="end" interval={0} />
                  <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={52} />
                  <Tooltip content={<Tip />} />
                  <Area type="monotone" dataKey="avg" name="Avg Daily Consumption"
                    stroke={T.blue} strokeWidth={2.5} fill="url(#dowGrad)"
                    dot={{r:5,fill:T.blue}} activeDot={{r:7}} />
                </AreaChart>
              </ResponsiveContainer>
            </Card>
          </>}

        </>}

        {/* ═══════════════════════════════
            TAB 5: MATERIAL DEEP DIVE
        ═══════════════════════════════ */}
        {tab==="material" && <>
          <Section>Material Deep Dive</Section>
          <div style={{ display:"flex", gap:12, alignItems:"center", marginBottom:18 }}>
            <span style={{ fontSize:13, fontWeight:600, color:T.gray600 }}>Select Material:</span>
            <MaterialSearch value={selected} onChange={setSelected} materials={materials} />
          </div>

          {detailLoading ? (
            <div style={{ textAlign:"center", color:T.gray400, padding:60 }}>Loading...</div>
          ) : matDetail && !matDetail.error && <>

            <div style={{ background:`linear-gradient(135deg,${T.blue},${T.blue2})`, borderRadius:12, padding:"18px 22px", marginBottom:14, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
              <div>
                <div style={{ fontSize:10, color:"rgba(255,255,255,0.6)", textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:5 }}>Material</div>
                <div style={{ fontSize:26, fontWeight:800, color:"#fff", fontFamily:"'IBM Plex Mono'" }}>{matDetail.material}</div>
                <div style={{ marginTop:8, display:"flex", gap:8, flexWrap:"wrap" }}>
                  <ABCBadge cls={matDetail.abc_class} />
                  <span style={{ background:"rgba(255,255,255,0.15)", color:"#fff", borderRadius:999, padding:"3px 11px", fontSize:11 }}>{matDetail.shop}</span>
                  <span style={{ background:"rgba(255,255,255,0.15)", color:"#fff", borderRadius:999, padding:"3px 11px", fontSize:11 }}>{matDetail.machine}</span>
                  <VendorBadge valType={matDetail.lead_time?.procurement?.includes("Import")?2:1} />
                </div>
              </div>
              <RiskBadge level={matDetail.risk} size={13} />
            </div>

            <div style={{ background:matDetail.risk==="High"?"#fef2f2":matDetail.risk==="Medium"?"#fffbeb":"#f0fdf4", border:`1px solid ${matDetail.risk==="High"?"#fca5a5":matDetail.risk==="Medium"?"#fcd34d":"#86efac"}`, borderRadius:10, padding:"11px 16px", marginBottom:14, fontSize:13, color:T.gray900 }}>
              {matDetail.alert}
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12, marginBottom:14 }}>
              <Card style={{ border:"1px solid #bfdbfe", background:"#eff6ff" }}>
                <div style={{ fontSize:11, fontWeight:700, color:"#3b82f6", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:10 }}>📊 Forecast</div>
                <div style={{ fontSize:10, color:T.gray400, marginBottom:8 }}>Forecast Source: AI Forecast Engine</div>
                {[
                  { label:"Predicted Next Month", value:fmtDisplay(matDetail.forecast?.predicted_next_month), big:true },
                  { label:"Current Month Consumption", value:fmtDisplay(matDetail.forecast?.current_month_consumption) },
                  { label:"Last Month",            value:fmtDisplay(matDetail.forecast?.last_month)            },
                ].map(s=>(
                  <div key={s.label} style={{ marginBottom:9 }}>
                    <div style={{ fontSize:10, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:2 }}>{s.label}</div>
                    <div style={{ fontSize:s.big?26:17, fontWeight:700, color:T.gray900 }}>{s.value}</div>
                  </div>
                ))}
              </Card>

              <Card style={{ border:"1px solid #bbf7d0", background:"#f0fdf4" }}>
                <div style={{ fontSize:11, fontWeight:700, color:"#16a34a", textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:10 }}>📦 Inventory</div>
                {[
                  { label:"Current Stock",  value:fmt(matDetail.inventory?.current_stock), big:true },
                  { label:"Safety Stock",   value:fmt(matDetail.inventory?.safety_stock)           },
                  { label:"Demand Gap",     value:fmtD(matDetail.inventory?.gap), color:matDetail.inventory?.gap>0?T.red:T.green },
                ].map(s=>(
                  <div key={s.label} style={{ marginBottom:9 }}>
                    <div style={{ fontSize:10, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:2 }}>{s.label}</div>
                    <div style={{ fontSize:s.big?26:17, fontWeight:700, color:s.color||T.gray900 }}>{s.value}</div>
                  </div>
                ))}
              </Card>

              <Card style={{ border:"1px solid #fde68a", background:"#fffbeb" }}>
                <div style={{ fontSize:11, fontWeight:700, color:T.orange, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:10 }}>🛒 Procurement</div>
                {[
                  { label:"Recommended Order Qty", value:fmt(matDetail.order?.recommended_qty), big:true },
                  { label:"Lead Time",              value:matDetail.lead_time?.total            },
                  { label:"Stock Runs Out",         value:matDetail.lead_time?.runout_date, color:matDetail.lead_time?.already_late?T.red:T.orange },
                  { label:"Reorder By",             value:matDetail.lead_time?.already_late?"🚨 ORDER TODAY":matDetail.lead_time?.reorder_by, color:matDetail.lead_time?.already_late?T.red:T.gray900 },
                  { label:"Vendor Type",            value:matDetail.lead_time?.procurement      },
                ].map(s=>(
                  <div key={s.label} style={{ marginBottom:9 }}>
                    <div style={{ fontSize:10, color:T.gray400, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:2 }}>{s.label}</div>
                    <div style={{ fontSize:s.big?26:12, fontWeight:s.big?700:600, color:s.color||T.gray900, fontFamily:s.big?"inherit":"'IBM Plex Mono'" }}>{s.value}</div>
                  </div>
                ))}
              </Card>
            </div>

            {/* Demand Intelligence KPI Cards */}
            <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:14 }}>
              {[
                { label: "Forecast Next Month", value: fmtDisplay(demandIntelligenceKPIs.forecastNext), color: T.blue2 },
                { label: "Current Month Consumption", value: fmtDisplay(demandIntelligenceKPIs.currentMonth) },
                { label: "Peak Consumption Month", value: demandIntelligenceKPIs.peakMonth },
                { label: "Lowest Consumption Month", value: demandIntelligenceKPIs.lowestMonth },
              ].map(k => (
                <div key={k.label} style={{ background: "#fff", border: `1px solid ${T.gray200}`, borderRadius: 10, padding: "14px 16px", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
                  <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: T.gray400, marginBottom: 5 }}>{k.label}</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: k.color || T.gray900, fontFamily: "'IBM Plex Mono'" }}>{k.value}</div>
                </div>
              ))}
            </div>

            <div style={{ display:"grid", gridTemplateColumns:"2fr 1fr", gap:14, marginBottom:14 }}>
              <Card>
                <CardTitle
                  title="Demand Intelligence — Actual vs Forecast"
                  sub="Blue Line = Actual Consumption · Orange Dotted Line = AI Recursive Multi-Step Forecast (each point predicted recursively using the previous forecast)"
                  right={
                    <div style={{ display:"flex", gap:8 }}>
                      <Sel value={trendYear}  onChange={setTrendYear}  options={histYears.map(y=>({value:y,label:y==="all"?`${currentYear} (Selected)`:y}))} />
                      <Sel value={trendMonth} onChange={setTrendMonth} options={MONTHS} />
                    </div>
                  }
                />
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12 }}>
                  <span style={{ background: T.orange + "15", color: T.orange, border: `1px solid ${T.orange}33`, borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 700 }}>
                    ⚡ AI Recursive Multi-Step Forecast: Each point is predicted recursively using the previous forecast
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={240}>
                  <ComposedChart data={forecastExtended} margin={{top:35,right:55,left:0,bottom:5}}>
                    <CartesianGrid strokeDasharray="3 3" stroke={T.gray100} vertical={false} />
                    <XAxis dataKey="date" tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={{stroke:T.gray200}} interval="preserveStartEnd" tickFormatter={formatXAxisDate} />
                    <YAxis tick={{fill:T.gray400,fontSize:10}} tickLine={false} axisLine={false} width={55} />
                    <Tooltip content={<Tip />} />
                    <Line type="monotone" dataKey="qty" name="Actual Consumption" stroke={T.blue} strokeWidth={3}
                      connectNulls={true}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        if (!cx || !cy) return null;
                        const isSpecial = payload.date === keyDates.peak || payload.date === keyDates.lowest || payload.date === keyDates.current;
                        return (
                          <circle cx={cx} cy={cy} r={isSpecial ? 6 : 4} fill={T.blue} stroke="#fff" strokeWidth={isSpecial ? 1.5 : 0} />
                        );
                      }}
                      activeDot={{r:6}}>
                      <LabelList dataKey="qty" position="top" content={(props) => {
                        const { x, y, value, index } = props;
                        if (value == null || !isFiniteNum(value)) return null;
                        const item = forecastExtended[index];
                        if (!item) return null;
                        const label = item.date === keyDates.peak ? "Peak: "
                                    : item.date === keyDates.lowest ? "Lowest: "
                                    : item.date === keyDates.current ? "Current: " : "";
                        const textStr = `${label}${fmt(value)}`;
                        return (
                          <text x={x} y={y - 10} fill={T.blue2} textAnchor="middle" fontSize={9} fontFamily="IBM Plex Mono" fontWeight="bold">
                            {textStr}
                          </text>
                        );
                      }} />
                    </Line>
                    <Line type="monotone" dataKey="forecast" name="Forecast" stroke={T.orange} strokeWidth={3} strokeDasharray="5 5"
                      connectNulls={true}
                      dot={(props) => {
                        const { cx, cy, payload } = props;
                        if (!cx || !cy) return null;
                        const isStart = payload.date === keyDates.forecastStart;
                        return (
                          <circle cx={cx} cy={cy} r={isStart ? 6 : 4} fill={T.orange} stroke="#fff" strokeWidth={isStart ? 1.5 : 0} />
                        );
                      }}
                      activeDot={{r:6}}>
                      <LabelList dataKey="forecast" position="top" content={(props) => {
                        const { x, y, value, index } = props;
                        if (value == null || !isFiniteNum(value)) return null;
                        const item = forecastExtended[index];
                        if (!item) return null;
                        
                        const forecastPoints = forecastExtended.filter(r => r.qty === null || r.qty === undefined);
                        const forecastIndex = forecastPoints.findIndex(r => r.date === item.date);
                        
                        const formattedDate = formatXAxisDate(item.date);
                        const label = item.date === keyDates.forecastStart ? "Start: " : "";
                        const textStr = `${label}${formattedDate ? `${formattedDate} : ` : ""}${fmt(value)}`;
                        
                        // Alternate y position: Month +1 (index 0) and Month +3 (index 2) go below the point
                        // Month +2 (index 1) goes above the point
                        const isBelow = forecastIndex === 0 || forecastIndex === 2;
                        const textY = isBelow ? y + 18 : y - 10;
                        
                        return (
                          <text x={x} y={textY} fill={T.orange} textAnchor="middle" fontSize={9} fontFamily="IBM Plex Mono" fontWeight="bold">
                            {textStr}
                          </text>
                        );
                      }} />
                    </Line>
                  </ComposedChart>
                </ResponsiveContainer>
              </Card>

              <Card p={0}>
                <div style={{ padding:"12px 14px", borderBottom:`1px solid ${T.gray100}` }}>
                  <div style={{ fontSize:13, fontWeight:700, color:T.gray900 }}>Recent History — {currentYear}</div>
                </div>
                <div style={{ maxHeight:270, overflowY:"auto" }}>
                  <table style={{ width:"100%", borderCollapse:"collapse", fontSize:11 }}>
                    <thead>
                      <tr style={{ background:T.gray50 }}>
                        {["Month","Qty","Status"].map(h=>(
                          <th key={h} style={{ padding:"7px 10px", textAlign:"left", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase", borderBottom:`1px solid ${T.gray200}` }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[...history.filter(r=>r.year===currentYear)].reverse().slice(0,20).map((h,i)=>{
                        const isPeak = h.date === keyDates.peak;
                        const isLow  = h.date === keyDates.lowest;
                        const isCur  = h.date === keyDates.current;
                        return (
                          <tr key={i} style={{ borderBottom:`1px solid ${T.gray100}` }}>
                            <td style={{ padding:"6px 10px", fontFamily:"'IBM Plex Mono'", color:T.gray900 }}>{h.date}</td>
                            <td style={{ padding:"6px 10px", fontFamily:"'IBM Plex Mono'" }}>{fmtD(h.qty)}</td>
                            <td style={{ padding:"6px 10px" }}>
                              <span style={{ background:isPeak?"#fef2f2":isLow?"#fffbeb":isCur?"#eff6ff":"#f0fdf4", color:isPeak?T.red:isLow?T.orange:isCur?T.blue2:T.green, borderRadius:999, padding:"2px 7px", fontSize:9, fontWeight:700 }}>
                                {isPeak?"Peak":isLow?"Lowest":isCur?"Current":"Normal"}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>

            {sameMachineMats.length > 0 && (
              <>
                <Section>Other At-Risk Materials on Same Machine: {matDetail.machine}</Section>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:10 }}>
                  {sameMachineMats.map((r,i)=>(
                    <div key={r.material} style={{ background:"#fff", border:`1px solid ${T.gray200}`, borderRadius:8, padding:"12px 14px", cursor:"pointer", borderTop:`3px solid ${r.risk==="High"?T.red:T.orange}` }}
                      onClick={()=>setSelected(r.material)}>
                      <div style={{ fontSize:13, fontWeight:700, color:T.blue, fontFamily:"'IBM Plex Mono'", marginBottom:6 }}>{r.material}</div>
                      <RiskBadge level={r.risk} />
                      <div style={{ fontSize:11, color:T.gray600, marginTop:6 }}>Stock: {fmt(r.inventory?.current_stock)}</div>
                      <div style={{ fontSize:11, color:T.gray600 }}>Runs out: {r.lead_time?.days_to_runout ?? "—"}d</div>
                    </div>
                  ))}
                </div>
              </>
            )}

          {/* ── Multi-Shop Procurement Validation ── */}
          {multiShopMaterials.length > 0 && (
            <>
            <Section>Multi-Shop Procurement Validation</Section>
            <Card style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: T.gray900, marginBottom: 4 }}>Materials with Multi-Shop Usage</div>
              <div style={{ fontSize: 11, color: T.gray400, marginBottom: 12 }}>These materials appear across multiple shops — procurement consolidation prevents duplicate purchase orders</div>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:11 }}>
                <thead>
                  <tr style={{ background:T.gray50 }}>
                    {["Material","Shop Count","Shops","Consolidated Order Qty","Risk"].map(h=>(
                      <th key={h} style={{ padding:"7px 10px", textAlign:"left", color:T.gray400, fontSize:10, textTransform:"uppercase", letterSpacing:"0.05em", borderBottom:`1px solid ${T.gray200}` }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {multiShopMaterials.map(c=>(
                    <tr key={c.material} style={{ borderBottom:`1px solid ${T.gray100}` }}>
                      <td style={{ padding:"8px 10px", fontWeight:700, color:T.blue, fontFamily:"'IBM Plex Mono'" }}>{c.material}</td>
                      <td style={{ padding:"8px 10px" }}>
                        <span style={{ background:"#eff6ff", color:T.blue2, borderRadius:999, padding:"2px 8px", fontSize:11, fontWeight:700 }}>
                          {c.shops.length} shops
                        </span>
                      </td>
                      <td style={{ padding:"8px 10px", color:T.gray600, fontSize:11 }}>{c.shops.join(", ")}</td>
                      <td style={{ padding:"8px 10px", fontFamily:"'IBM Plex Mono'", fontWeight:700, color:T.gray900 }}>{fmt(Math.round(c.total_recommended_qty))}</td>
                      <td style={{ padding:"8px 10px" }}><RiskBadge level={c.highest_risk} size={10} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div style={{ marginTop:10, padding:"8px 12px", background:"#f0fdf4", borderRadius:6, border:`1px solid #86efac`, fontSize:11, color:T.green }}>
                ✓ Procurement exposure in Executive Overview uses consolidated order quantities — no double counting
              </div>
            </Card>
            </>
          )}
        </>}
        </>}

        {/* ═══════════════════════════════
            TAB 6: MORNING MEETING
        ═══════════════════════════════ */}
        {tab==="morning" && <>

          {/* Header bar */}
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:18 }}>
            <div>
              <div style={{ fontSize:20, fontWeight:800, color:T.blue }}>☀ Morning Meeting</div>
              <div style={{ fontSize:12, color:T.gray400, marginTop:3 }}>
                As of <strong style={{color:T.gray900}}>{mmYesterdayLabel}</strong> · {mmFYLabel} · {mmMonthsElapsed} months elapsed
              </div>
            </div>
            <div style={{ display:"flex", gap:10 }}>
              <button
                onClick={()=>{
                  if (!mmPin) {
                    setMmPinStep("setpin");
                  } else {
                    setMmPinStep("verify");
                  }
                  setMmPinInput(""); setMmPinError(""); setMmShowBudgetModal(true);
                }}
                style={{ background:T.blue, color:"#fff", border:"none", borderRadius:7, padding:"8px 18px", fontSize:12, fontWeight:700, cursor:"pointer", display:"flex", alignItems:"center", gap:6 }}>
                🔒 Set FY Budget
              </button>
            </div>
          </div>

          {/* KPI summary row */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:12, marginBottom:20 }}>
            {[
              { label:"YTD Consumption", value: fmtK(mmYTD.total), color:T.blue,   bg:"#eff6ff" },
              { label:"YTD Budget",      value: fmtK(mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0)), color:"#92400e", bg:"#fffbeb" },
              { label:"YTD Balance",     value: fmtK(mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) - mmYTD.total), color:T.green, bg:"#f0fdf4" },
              { label:`${mmFYLabel} Budget`, value: fmtK(mmGetTotalAnnualBudget()), color:T.gray900, bg:T.gray50 },
              { label:"% vs YTD Budget", value: mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) > 0
                  ? (mmYTD.total / mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) * 100).toFixed(1)+"%"
                  : "—",
                color: mmYTD.total > mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) ? T.red : T.green,
                bg: mmYTD.total > mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) ? "#fef2f2" : "#f0fdf4" },
            ].map(k=>(
              <div key={k.label} style={{ background:k.bg, border:`1px solid ${T.gray200}`, borderRadius:10, padding:"14px 16px" }}>
                <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em", color:T.gray400, marginBottom:5 }}>{k.label}</div>
                <div style={{ fontSize:22, fontWeight:800, color:k.color, fontFamily:"'IBM Plex Mono'" }}>{k.value}</div>
              </div>
            ))}
          </div>

          {/* Main matrix */}
          {mmLoadingAll ? (
            <div style={{ textAlign:"center", padding:60, color:T.gray400 }}>Loading morning meeting data...</div>
          ) : (
            <Card p={0} style={{ marginBottom:20 }}>
              <div style={{ overflowX:"auto", overflowY:"auto", maxHeight:620 }}>
                <table style={{ borderCollapse:"collapse", fontSize:11, minWidth:"100%" }}>
                  <thead style={{ position:"sticky", top:0, zIndex:20 }}>
                    <tr style={{ background:T.blue }}>
                      <th style={{ position:"sticky", left:0, zIndex:30, background:T.blue, padding:"10px 14px", textAlign:"left", fontSize:10, fontWeight:700, color:"#fff", textTransform:"uppercase", letterSpacing:"0.06em", minWidth:140, borderRight:`1px solid rgba(255,255,255,0.2)` }}>Parameter</th>
                      {mmShops.map(s=>(
                        <th key={s} style={{ padding:"10px 8px", fontSize:10, fontWeight:700, color:"#fff", textTransform:"uppercase", whiteSpace:"nowrap", textAlign:"center", minWidth:72, borderRight:`1px solid rgba(255,255,255,0.15)` }}>{s}</th>
                      ))}
                      <th style={{ padding:"10px 10px", fontSize:10, fontWeight:800, color:"#fff", textTransform:"uppercase", textAlign:"center", minWidth:72, background:"rgba(0,0,0,0.2)" }}>Total</th>
                    </tr>
                  </thead>
                  <tbody>

                    {/* Yesterday row */}
                    <tr style={{ background:"#e0f2fe", borderBottom:`2px solid #0ea5e9` }}>
                      <td style={{ position:"sticky", left:0, background:"#e0f2fe", padding:"9px 14px", fontWeight:800, color:"#0369a1", borderRight:`1px solid ${T.gray200}`, fontSize:11, whiteSpace:"nowrap" }}>
                        📅 {mmYesterdayLabel}
                      </td>
                      {mmShops.map(s=>(
                        <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, color:"#0369a1", fontWeight:700, borderRight:`1px solid ${T.gray100}` }}>
                          {mmYesterdayRow[s] > 0 ? fmt(mmYesterdayRow[s]) : "—"}
                        </td>
                      ))}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, color:"#0369a1", background:"#bae6fd" }}>
                        {fmt(mmYesterdayRow.total || 0)}
                      </td>
                    </tr>

                    {/* Monthly rows */}
                    {mmFYMonths.map((monthStr, idx)=>{
                      const row = mmMatrix[monthStr] || {};
                      const total = mmShops.reduce((s,sh)=>s+(row[sh]||0),0);
                      const [yr,mo] = monthStr.split("-").map(Number);
                      const monthNames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
                      const label = `${monthNames[mo-1]}'${String(yr).slice(2)}`;
                      const isCurrentMonth = monthStr === `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,"0")}`;
                      const rowBg = isCurrentMonth ? "#fefce8" : idx%2===0 ? "#fff" : "#fafafa";
                      return (
                        <tr key={monthStr} style={{ background:rowBg, borderBottom:`1px solid ${T.gray100}` }}>
                          <td style={{ position:"sticky", left:0, background:rowBg, padding:"8px 14px", fontWeight:isCurrentMonth?800:600, color:isCurrentMonth?T.orange:T.gray700, borderRight:`1px solid ${T.gray200}`, fontSize:11, whiteSpace:"nowrap" }}>
                            {isCurrentMonth ? `⚡ ${label} (MTD)` : label}
                          </td>
                          {mmShops.map(s=>{
                            const val = row[s]||0;
                            const bgt = mmGetMonthlyBudget(s);
                            const cellBg = bgt > 0 ? (val > bgt ? "#fef2f2" : "#f0fdf4") : "transparent";
                            return (
                              <td key={s} style={{ padding:"8px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, color:T.gray900, background:cellBg, borderRight:`1px solid ${T.gray100}` }}>
                                {val > 0 ? fmt(Math.round(val)) : "—"}
                              </td>
                            );
                          })}
                          <td style={{ padding:"8px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color:T.gray900, background:"#f1f5f9" }}>
                            {total > 0 ? fmt(Math.round(total)) : "—"}
                          </td>
                        </tr>
                      );
                    })}

                    {/* ── Summary separator ── */}
                    <tr><td colSpan={mmShops.length+2} style={{ height:6, background:T.gray200 }} /></tr>

                    {/* YTD Consumption */}
                    <tr style={{ background:"#fed7aa", borderBottom:`1px solid #ea580c` }}>
                      <td style={{ position:"sticky", left:0, background:"#fed7aa", padding:"9px 14px", fontWeight:800, color:"#9a3412", borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>YTD Consumption</td>
                      {mmShops.map(s=>(
                        <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color:"#9a3412", borderRight:`1px solid rgba(234,88,12,0.2)` }}>
                          {fmt(Math.round(mmYTD[s]||0))}
                        </td>
                      ))}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, color:"#9a3412", background:"#fdba74" }}>
                        {fmt(Math.round(mmYTD.total||0))}
                      </td>
                    </tr>

                    {/* YTD Budget */}
                    <tr style={{ background:"#fef9c3", borderBottom:`1px solid #ca8a04` }}>
                      <td style={{ position:"sticky", left:0, background:"#fef9c3", padding:"9px 14px", fontWeight:800, color:"#713f12", borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>YTD Budget</td>
                      {mmShops.map(s=>{
                        const ytdBgt = mmGetYTDBudget(s);
                        return (
                          <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color:"#713f12", borderRight:`1px solid rgba(202,138,4,0.2)` }}>
                            {ytdBgt > 0 ? fmt(Math.round(ytdBgt)) : "—"}
                          </td>
                        );
                      })}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, color:"#713f12", background:"#fde68a" }}>
                        {mmGetTotalAnnualBudget() > 0 ? fmt(Math.round(mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0))) : "—"}
                      </td>
                    </tr>

                    {/* YTD Balance Budget */}
                    <tr style={{ background:"#c2410c22", borderBottom:`2px solid #c2410c` }}>
                      <td style={{ position:"sticky", left:0, background:"#fddcb5", padding:"9px 14px", fontWeight:800, color:"#7c2d12", borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>YTD Balance Budget</td>
                      {mmShops.map(s=>{
                        const bal = mmGetYTDBudget(s) - (mmYTD[s]||0);
                        return (
                          <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color: bal >= 0 ? T.green : T.red, background:"#fddcb5", borderRight:`1px solid rgba(194,65,12,0.2)` }}>
                            {mmGetYTDBudget(s) > 0 ? fmt(Math.round(bal)) : "—"}
                          </td>
                        );
                      })}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, background:"#fdba74" }}>
                        {(() => { const b = mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0) - mmYTD.total; return mmGetTotalAnnualBudget()>0 ? <span style={{color:b>=0?T.green:T.red}}>{fmt(Math.round(b))}</span> : "—"; })()}
                      </td>
                    </tr>

                    {/* FY Budget */}
                    <tr style={{ background:T.gray50, borderBottom:`1px solid ${T.gray200}` }}>
                      <td style={{ position:"sticky", left:0, background:T.gray50, padding:"9px 14px", fontWeight:700, color:T.gray900, borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>{mmFYLabel} Budget</td>
                      {mmShops.map(s=>(
                        <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, color:T.gray600, borderRight:`1px solid ${T.gray100}` }}>
                          {mmGetAnnualBudget(s) > 0 ? fmt(mmGetAnnualBudget(s)) : "—"}
                        </td>
                      ))}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color:T.gray900, background:T.gray100 }}>
                        {mmGetTotalAnnualBudget() > 0 ? fmt(mmGetTotalAnnualBudget()) : "—"}
                      </td>
                    </tr>

                    {/* FY Balance Budget */}
                    <tr style={{ background:T.gray50, borderBottom:`1px solid ${T.gray200}` }}>
                      <td style={{ position:"sticky", left:0, background:T.gray50, padding:"9px 14px", fontWeight:700, color:T.gray900, borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>{mmFYLabel} Balance Budget</td>
                      {mmShops.map(s=>{
                        const bal = mmGetAnnualBudget(s) - (mmYTD[s]||0);
                        return (
                          <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:600, color: mmGetAnnualBudget(s)>0 ? (bal>=0?T.green:T.red) : T.gray400, borderRight:`1px solid ${T.gray100}` }}>
                            {mmGetAnnualBudget(s) > 0 ? fmt(Math.round(bal)) : "—"}
                          </td>
                        );
                      })}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, background:T.gray100 }}>
                        {(() => { const b = mmGetTotalAnnualBudget() - mmYTD.total; return mmGetTotalAnnualBudget()>0 ? <span style={{color:b>=0?T.green:T.red}}>{fmt(Math.round(b))}</span> : "—"; })()}
                      </td>
                    </tr>

                    {/* % YTD Cons / YTD Budget */}
                    <tr style={{ background:"#f8fafc", borderBottom:`1px solid ${T.gray200}` }}>
                      <td style={{ position:"sticky", left:0, background:"#f8fafc", padding:"9px 14px", fontWeight:700, color:T.gray900, borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>% YTD Cons/YTD Budget</td>
                      {mmShops.map(s=>{
                        const ytdBgt = mmGetYTDBudget(s);
                        const pct = ytdBgt > 0 ? ((mmYTD[s]||0)/ytdBgt*100) : null;
                        return (
                          <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color: pct==null?T.gray400:pct>100?T.red:T.green, borderRight:`1px solid ${T.gray100}` }}>
                            {pct != null ? pct.toFixed(1)+"%" : "—"}
                          </td>
                        );
                      })}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, background:T.gray100 }}>
                        {(()=>{
                          const tot = mmShops.reduce((s,sh)=>s+mmGetYTDBudget(sh),0);
                          const pct = tot > 0 ? (mmYTD.total/tot*100) : null;
                          return pct != null ? <span style={{color:pct>100?T.red:T.green}}>{pct.toFixed(1)}%</span> : "—";
                        })()}
                      </td>
                    </tr>

                    {/* % YTD / FY Budget */}
                    <tr style={{ background:"#f8fafc" }}>
                      <td style={{ position:"sticky", left:0, background:"#f8fafc", padding:"9px 14px", fontWeight:700, color:T.gray900, borderRight:`1px solid ${T.gray200}`, fontSize:11 }}>% YTD / {mmFYLabel} Budget</td>
                      {mmShops.map(s=>{
                        const fyBgt = mmGetAnnualBudget(s);
                        const pct = fyBgt > 0 ? ((mmYTD[s]||0)/fyBgt*100) : null;
                        return (
                          <td key={s} style={{ padding:"9px 8px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color: pct==null?T.gray400:pct>100?T.red:T.green, borderRight:`1px solid ${T.gray100}` }}>
                            {pct != null ? pct.toFixed(1)+"%" : "—"}
                          </td>
                        );
                      })}
                      <td style={{ padding:"9px 10px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:800, background:T.gray100 }}>
                        {(()=>{
                          const fyTot = mmGetTotalAnnualBudget();
                          const pct = fyTot > 0 ? (mmYTD.total/fyTot*100) : null;
                          return pct != null ? <span style={{color:pct>100?T.red:T.green}}>{pct.toFixed(1)}%</span> : "—";
                        })()}
                      </td>
                    </tr>

                  </tbody>
                </table>
              </div>

              {/* Legend */}
              <div style={{ padding:"10px 16px", borderTop:`1px solid ${T.gray200}`, display:"flex", gap:16, fontSize:11, color:T.gray400, flexWrap:"wrap" }}>
                <span style={{ display:"flex", alignItems:"center", gap:5 }}><span style={{ width:12,height:12,borderRadius:2,background:"#f0fdf4",border:`1px solid #86efac`,display:"inline-block" }}/>Under budget</span>
                <span style={{ display:"flex", alignItems:"center", gap:5 }}><span style={{ width:12,height:12,borderRadius:2,background:"#fef2f2",border:`1px solid #fca5a5`,display:"inline-block" }}/>Over budget</span>
                <span style={{ display:"flex", alignItems:"center", gap:5 }}><span style={{ width:12,height:12,borderRadius:2,background:"#fefce8",border:`1px solid #fde047`,display:"inline-block" }}/>Current month (MTD)</span>
                <span style={{ marginLeft:"auto", color:T.gray400 }}>Budget cells show — when no budget is set · Click 🔒 Set FY Budget to configure</span>
              </div>
            </Card>
          )}

        </>}

        {/* ── BUDGET MODAL ── */}
        {mmShowBudgetModal && (
          <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.5)", zIndex:1000, display:"flex", alignItems:"center", justifyContent:"center" }}
            onClick={(e)=>{ if(e.target===e.currentTarget){ setMmShowBudgetModal(false); setMmPinInput(""); setMmPinError(""); }}}>
            <div style={{ background:"#fff", borderRadius:14, padding:28, minWidth:420, maxWidth:560, boxShadow:"0 20px 60px rgba(0,0,0,0.3)" }}
              onClick={e=>e.stopPropagation()}>

              {/* Set PIN first time */}
              {mmPinStep==="setpin" && <>
                <div style={{ fontSize:16, fontWeight:800, color:T.gray900, marginBottom:6 }}>🔒 Set Budget PIN</div>
                <div style={{ fontSize:12, color:T.gray400, marginBottom:18 }}>Create a 4-digit PIN to protect budget editing. Keep it safe — only you will know it.</div>
                <div style={{ marginBottom:12 }}>
                  <div style={{ fontSize:11, fontWeight:700, color:T.gray600, marginBottom:5 }}>New PIN (4 digits)</div>
                  <input type="password" maxLength={4} value={mmNewPin} onChange={e=>setMmNewPin(e.target.value.replace(/\D/g,""))}
                    style={{ width:"100%", border:`1px solid ${T.gray200}`, borderRadius:7, padding:"9px 12px", fontSize:16, fontFamily:"'IBM Plex Mono'", letterSpacing:"0.3em", outline:"none" }}
                    placeholder="••••" />
                </div>
                <div style={{ marginBottom:18 }}>
                  <div style={{ fontSize:11, fontWeight:700, color:T.gray600, marginBottom:5 }}>Confirm PIN</div>
                  <input type="password" maxLength={4} value={mmNewPinConfirm} onChange={e=>setMmNewPinConfirm(e.target.value.replace(/\D/g,""))}
                    style={{ width:"100%", border:`1px solid ${T.gray200}`, borderRadius:7, padding:"9px 12px", fontSize:16, fontFamily:"'IBM Plex Mono'", letterSpacing:"0.3em", outline:"none" }}
                    placeholder="••••" />
                </div>
                {mmPinError && <div style={{ color:T.red, fontSize:12, marginBottom:12 }}>{mmPinError}</div>}
                <div style={{ display:"flex", gap:10 }}>
                  <button onClick={()=>setMmShowBudgetModal(false)} style={{ flex:1, background:T.gray50, border:`1px solid ${T.gray200}`, borderRadius:7, padding:"9px", fontSize:12, fontWeight:600, cursor:"pointer", color:T.gray600 }}>Cancel</button>
                  <button onClick={()=>{
                    if (mmNewPin.length !== 4) { setMmPinError("PIN must be exactly 4 digits"); return; }
                    if (mmNewPin !== mmNewPinConfirm) { setMmPinError("PINs do not match"); return; }
                    mmSavePin(mmNewPin);
                    setMmBudgetDraft({...mmBudget});
                    setMmPinStep("edit");
                    setMmPinError("");
                  }} style={{ flex:1, background:T.blue, color:"#fff", border:"none", borderRadius:7, padding:"9px", fontSize:12, fontWeight:700, cursor:"pointer" }}>
                    Set PIN & Continue →
                  </button>
                </div>
              </>}

              {/* Verify PIN */}
              {mmPinStep==="verify" && <>
                <div style={{ fontSize:16, fontWeight:800, color:T.gray900, marginBottom:6 }}>🔒 Budget Access</div>
                <div style={{ fontSize:12, color:T.gray400, marginBottom:20 }}>Enter your 4-digit PIN to edit the {mmFYLabel} budget.</div>
                <input type="password" maxLength={4} value={mmPinInput}
                  onChange={e=>setMmPinInput(e.target.value.replace(/\D/g,""))}
                  onKeyDown={e=>{ if(e.key==="Enter"){ if(mmPinInput===mmPin){ setMmBudgetDraft({...mmBudget}); setMmPinStep("edit"); setMmPinError(""); } else { setMmPinError("Incorrect PIN. Try again."); }}}}
                  style={{ width:"100%", border:`1px solid ${mmPinError?T.red:T.gray200}`, borderRadius:7, padding:"12px", fontSize:22, fontFamily:"'IBM Plex Mono'", textAlign:"center", letterSpacing:"0.5em", outline:"none", marginBottom:8 }}
                  placeholder="••••" autoFocus />
                {mmPinError && <div style={{ color:T.red, fontSize:12, marginBottom:10 }}>{mmPinError}</div>}
                <div style={{ display:"flex", gap:10, marginTop:8 }}>
                  <button onClick={()=>setMmShowBudgetModal(false)} style={{ flex:1, background:T.gray50, border:`1px solid ${T.gray200}`, borderRadius:7, padding:"9px", fontSize:12, fontWeight:600, cursor:"pointer", color:T.gray600 }}>Cancel</button>
                  <button onClick={()=>{
                    if(mmPinInput===mmPin){ setMmBudgetDraft({...mmBudget}); setMmPinStep("edit"); setMmPinError(""); }
                    else { setMmPinError("Incorrect PIN. Try again."); }
                  }} style={{ flex:1, background:T.blue, color:"#fff", border:"none", borderRadius:7, padding:"9px", fontSize:12, fontWeight:700, cursor:"pointer" }}>
                    Unlock →
                  </button>
                </div>
              </>}

              {/* Edit budget */}
              {mmPinStep==="edit" && <>
                <div style={{ fontSize:16, fontWeight:800, color:T.gray900, marginBottom:4 }}>📊 {mmFYLabel} Annual Budget</div>
                <div style={{ fontSize:12, color:T.gray400, marginBottom:16 }}>Enter total annual units budget per shop. Divided equally across 12 months automatically.</div>
                <div style={{ maxHeight:360, overflowY:"auto", marginBottom:16 }}>
                  <table style={{ width:"100%", borderCollapse:"collapse" }}>
                    <thead>
                      <tr style={{ background:T.gray50 }}>
                        <th style={{ padding:"8px 12px", textAlign:"left", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase" }}>Shop</th>
                        <th style={{ padding:"8px 12px", textAlign:"right", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase" }}>Annual Budget (units)</th>
                        <th style={{ padding:"8px 12px", textAlign:"right", fontSize:10, fontWeight:700, color:T.gray400, textTransform:"uppercase" }}>Monthly (÷12)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mmShops.map(s=>(
                        <tr key={s} style={{ borderBottom:`1px solid ${T.gray100}` }}>
                          <td style={{ padding:"8px 12px", fontWeight:700, color:T.blue2, fontSize:12 }}>{s}</td>
                          <td style={{ padding:"6px 12px", textAlign:"right" }}>
                            <input
                              type="number" min={0}
                              value={mmBudgetDraft[s] ?? ""}
                              onChange={e=>setMmBudgetDraft(prev=>({...prev,[s]:Number(e.target.value)}))}
                              style={{ width:120, border:`1px solid ${T.gray200}`, borderRadius:5, padding:"5px 8px", fontSize:12, fontFamily:"'IBM Plex Mono'", textAlign:"right", outline:"none" }}
                              placeholder="0"
                            />
                          </td>
                          <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, color:T.gray400 }}>
                            {mmBudgetDraft[s] > 0 ? fmt(Math.round(mmBudgetDraft[s]/12)) : "—"}
                          </td>
                        </tr>
                      ))}
                      <tr style={{ background:T.gray50, borderTop:`2px solid ${T.gray200}` }}>
                        <td style={{ padding:"8px 12px", fontWeight:800, color:T.gray900, fontSize:12 }}>Total</td>
                        <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontWeight:800, color:T.blue, fontSize:12 }}>
                          {fmt(Object.values(mmBudgetDraft).reduce((s,v)=>s+(Number(v)||0),0))}
                        </td>
                        <td style={{ padding:"8px 12px", textAlign:"right", fontFamily:"'IBM Plex Mono'", fontSize:11, color:T.gray400 }}>
                          {fmt(Math.round(Object.values(mmBudgetDraft).reduce((s,v)=>s+(Number(v)||0),0)/12))}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div style={{ display:"flex", gap:10 }}>
                  <button onClick={()=>setMmShowBudgetModal(false)} style={{ flex:1, background:T.gray50, border:`1px solid ${T.gray200}`, borderRadius:7, padding:"9px", fontSize:12, fontWeight:600, cursor:"pointer", color:T.gray600 }}>Cancel</button>
                  <button onClick={()=>{
                    mmSaveBudget(mmBudgetDraft);
                    setMmShowBudgetModal(false);
                    setMmPinStep("locked");
                  }} style={{ flex:2, background:T.green, color:"#fff", border:"none", borderRadius:7, padding:"9px", fontSize:12, fontWeight:700, cursor:"pointer" }}>
                    ✓ Save Budget
                  </button>
                </div>
              </>}

            </div>
          </div>
        )}

        {tab==="developer" && <>
          <Section>Forecast Engine Health</Section>
          {forecastEngine && (
            <Card style={{ marginBottom: 20 }}>
              <div style={{ display:"grid", gridTemplateColumns:"repeat(5,1fr)", gap:14, marginBottom:16 }}>
                {[
                  { label:"Current Model", value: forecastEngine.best_model },
                  { label:"MAE", value: fmtDisplay(forecastEngine.best_mae) },
                  { label:"Training Records", value: fmtDisplay(forecastEngine.dataset_size) },
                  { label:"Last Training Date", value: forecastEngine.last_training_date || "—" },
                  { label:"Fallback Usage", value: `${fallbackUsagePct}%` },
                ].map(k=>(
                  <div key={k.label} style={{ background:T.gray50, border:`1px solid ${T.gray200}`, borderRadius:8, padding:"10px 14px" }}>
                    <div style={{ fontSize:10, fontWeight:700, textTransform:"uppercase", color:T.gray400, marginBottom:4 }}>{k.label}</div>
                    <div style={{ fontSize:13, fontWeight:800, color:T.gray900, fontFamily:"'IBM Plex Mono'" }}>{k.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize:12, color:T.gray600, marginBottom:10 }}>
                <strong>Forecast Type:</strong> {forecastEngine.forecast_type} · <strong>Features:</strong> {(forecastEngine.features||[]).join(", ")}
              </div>
              <div style={{ fontSize:12, fontWeight:700, color:T.gray900, marginBottom:8 }}>Model Leaderboard</div>
              <table style={{ width:"100%", borderCollapse:"collapse", fontSize:11, marginBottom:12 }}>
                <thead>
                  <tr style={{ background:T.gray50 }}>
                    {["Rank","Model","MAE"].map(h=>(
                      <th key={h} style={{ padding:"7px 10px", textAlign:"left", fontSize:10, color:T.gray400, textTransform:"uppercase" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(forecastEngine.leaderboard||[]).map((row,i)=>(
                    <tr key={row.model} style={{ borderBottom:`1px solid ${T.gray100}`, background: row.model===forecastEngine.best_model ? "#eff6ff" : "#fff" }}>
                      <td style={{ padding:"7px 10px", fontFamily:"'IBM Plex Mono'" }}>{i+1}</td>
                      <td style={{ padding:"7px 10px", fontWeight:700 }}>{row.model}{row.model===forecastEngine.best_model?" ★":""}</td>
                      <td style={{ padding:"7px 10px", fontFamily:"'IBM Plex Mono'" }}>{fmtDisplay(row.mae)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {procurement.length > 0 && (
                <div style={{ fontSize:11, color:T.gray600 }}>
                  <strong>Fallback Status:</strong>{" "}
                  {procurement.filter(r=>r.developer?.fallback_used).length} of {procurement.length} materials used fallback_forecast()
                </div>
              )}
            </Card>
          )}

          {dashboardValidation && <>
          <Section>Dashboard Metric Audit & Validation — {currentYear}</Section>
          <Card p={0} style={{ marginBottom: 20 }}>
            <div style={{ padding:"12px 16px", borderBottom:`1px solid ${T.gray100}`, display:"flex", alignItems:"center", justifyContent:"space-between" }}>
              <div>
                <div style={{ fontSize:13, fontWeight:700, color:T.gray900 }}>Validation Layer</div>
                <div style={{ fontSize:11, color:T.gray400, marginTop:2 }}>Backend API values compared to source dataset aggregations</div>
              </div>
              <span style={{ background:dashboardValidation.overall_status==="PASS"?"#f0fdf4":"#fef2f2", color:dashboardValidation.overall_status==="PASS"?T.green:T.red, borderRadius:999, padding:"4px 12px", fontSize:11, fontWeight:800 }}>
                {dashboardValidation.overall_status}
              </span>
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1.3fr", gap:0 }}>
              <div style={{ padding:14, borderRight:`1px solid ${T.gray100}` }}>
                {(dashboardValidation.checks||[]).map(c=>(
                  <div key={c.metric} style={{ display:"flex", justifyContent:"space-between", alignItems:"center", padding:"7px 0", borderBottom:`1px solid ${T.gray100}` }}>
                    <span style={{ fontSize:12, color:T.gray600 }}>{c.metric}</span>
                    <span style={{ fontFamily:"'IBM Plex Mono'", fontSize:11, fontWeight:700, color:c.status==="PASS"?T.green:T.red }}>
                      {c.status} · {Number(c.mismatch_pct||0).toFixed(3)}%
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ padding:14 }}>
                <div style={{ fontSize:12, fontWeight:700, color:T.gray900, marginBottom:8 }}>Shop Validation</div>
                <table style={{ width:"100%", borderCollapse:"collapse", fontSize:11 }}>
                  <thead>
                    <tr style={{ background:T.gray50 }}>
                      {["Shop","Dashboard Value","Dataset Value","Match"].map(h=>(
                        <th key={h} style={{ padding:"7px 8px", textAlign:"left", color:T.gray400, fontSize:10, textTransform:"uppercase" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {(dashboardValidation.shop_validation||[]).map(row=>(
                      <tr key={row.shop} style={{ borderBottom:`1px solid ${T.gray100}` }}>
                        <td style={{ padding:"7px 8px", color:T.gray600 }}>{row.shop}</td>
                        <td style={{ padding:"7px 8px", fontFamily:"'IBM Plex Mono'" }}>{fmt(row.dashboard_value)}</td>
                        <td style={{ padding:"7px 8px", fontFamily:"'IBM Plex Mono'" }}>{fmt(row.dataset_value)}</td>
                        <td style={{ padding:"7px 8px", fontWeight:700, color:row.match?T.green:T.red }}>{row.match ? "Match" : "No Match"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </Card>
          
          <Card style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: T.gray900, marginBottom: 10 }}>Backend Architectural Details</div>
            <div style={{ fontSize: 12, color: T.gray600, lineHeight: "1.6" }}>
              <p style={{ marginBottom: 8 }}><strong>Forecast Method:</strong> {dashboardValidation.forecast_method?.name}</p>
              <p style={{ marginBottom: 8 }}><strong>Engine:</strong> {dashboardValidation.forecast_method?.engine} · <strong>Best Model:</strong> {dashboardValidation.forecast_method?.best_model} (MAE: {dashboardValidation.forecast_method?.best_mae})</p>
              <p style={{ marginBottom: 8 }}><strong>Fallback Policy:</strong> {dashboardValidation.forecast_method?.fallback}</p>
              <p style={{ marginBottom: 8 }}><strong>Value Metric Note:</strong> {dashboardValidation.value_metric_note}</p>
              {dashboardValidation.safety_stock_proof && (
                <div style={{ marginTop: 12, padding: 12, background: T.gray50, borderRadius: 8, border: `1px solid ${T.gray200}` }}>
                  <div style={{ fontWeight: 700, color: T.gray900, marginBottom: 6 }}>Safety Stock Math Proof ({dashboardValidation.safety_stock_proof.material})</div>
                  <ul style={{ paddingLeft: 20 }}>
                    <li>Backend Recommended: {fmtDisplay(dashboardValidation.safety_stock_proof.backend_recommended_qty)} (Formula: <code>{dashboardValidation.safety_stock_proof.backend_formula}</code>)</li>
                    <li>Duplicate Frontend Recommended: {fmtDisplay(dashboardValidation.safety_stock_proof.duplicate_frontend_qty)} (Formula: <code>{dashboardValidation.safety_stock_proof.duplicate_frontend_formula}</code>)</li>
                    <li>Audit Result: Overstatement of {fmtDisplay(dashboardValidation.safety_stock_proof.duplicate_overstatement_units)} units resolved in this version.</li>
                  </ul>
                </div>
              )}
            </div>
          </Card>
          </>}
        </>}

      </div>

      {/* Footer */}
      <div style={{ background:"#fff", borderTop:`1px solid ${T.gray200}`, padding:"10px 28px", display:"flex", justifyContent:"space-between", alignItems:"center", marginTop:28 }}>
        <span style={{ fontSize:11, color:T.gray400 }}>Tata Motors — Spare Parts Inventory Intelligence System © 2025</span>
        <span style={{ fontSize:11, color:T.gray400, fontFamily:"'IBM Plex Mono'" }}>SpareAI v4.0 · AI Forecast Engine</span>
      </div>
    </div>
  );
} 