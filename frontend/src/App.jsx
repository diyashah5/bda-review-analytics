import { useEffect, useState } from 'react'
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  CircleHelp,
  LoaderCircle,
  MessageSquareText,
  Search,
  Sparkles,
  Star,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const API = '/api'
const SENTIMENT_COLORS = {
  positive: '#277a58',
  neutral: '#d8952b',
  negative: '#c55348',
}

async function request(path, options) {
  const response = await fetch(`${API}${path}`, options)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}))
    throw new Error(detail.detail || `Request failed (${response.status})`)
  }
  return response.json()
}

function formatNumber(value) {
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(value || 0)
}

function App() {
  const [options, setOptions] = useState({ categories: [], price_bands: [] })
  const [category, setCategory] = useState('')
  const [priceBand, setPriceBand] = useState('')
  const [summary, setSummary] = useState(null)
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [review, setReview] = useState('Very good quality, totally worth the money')
  const [prediction, setPrediction] = useState(null)
  const [predicting, setPredicting] = useState(false)

  useEffect(() => {
    request('/analytics/filters')
      .then(setOptions)
      .catch((problem) => setError(problem.message))
  }, [])

  useEffect(() => {
    const params = new URLSearchParams()
    if (category) params.set('category', category)
    if (priceBand) params.set('price_band', priceBand)
    const query = params.size ? `?${params}` : ''
    let current = true
    setLoading(true)
    Promise.all([
      request(`/analytics/summary${query}`),
      request(`/analytics/products?limit=12${category ? `&category=${encodeURIComponent(category)}` : ''}`),
    ])
      .then(([nextSummary, nextProducts]) => {
        if (!current) return
        setSummary(nextSummary)
        setProducts(nextProducts)
        setError('')
      })
      .catch((problem) => {
        if (current) setError(problem.message)
      })
      .finally(() => {
        if (current) setLoading(false)
      })
    return () => { current = false }
  }, [category, priceBand])

  async function submitReview(event) {
    event.preventDefault()
    setPredicting(true)
    setPrediction(null)
    try {
      setPrediction(await request('/predict/sentiment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: review }),
      }))
    } catch (problem) {
      setPrediction({ error: problem.message })
    } finally {
      setPredicting(false)
    }
  }

  const sentimentData = summary
    ? Object.entries(summary.sentiment_counts).map(([name, value]) => ({ name, value }))
    : []
  const positiveShare = summary?.reviews
    ? (100 * (summary.sentiment_counts.positive || 0)) / summary.reviews
    : 0
  const negativeShare = summary?.reviews
    ? (100 * (summary.sentiment_counts.negative || 0)) / summary.reviews
    : 0

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="Flipkart Review Intelligence home">
          <span className="brand-mark"><BarChart3 size={20} /></span>
          <span><strong>VOICE / DATA</strong><small>FLIPKART REVIEW INTELLIGENCE</small></span>
        </a>
        <div className="topbar-meta"><span className="live-dot" /> ANALYTICS WORKSPACE <span className="topbar-divider" /> BDA MINI PROJECT</div>
      </header>

      <main id="top" className="main-content">
        <section className="page-heading">
          <div>
            <p className="eyebrow">CUSTOMER SIGNALS · INDIA</p>
            <h1>Review intelligence</h1>
            <p className="heading-copy">A large-scale read on product experience, price, and sentiment.</p>
          </div>
          <div className="dataset-stamp"><span>DATASET</span><strong>164,982</strong><small>clean reviews · Spark Silver</small></div>
        </section>

        <section className="filter-row" aria-label="Dashboard filters">
          <div className="filter-label"><Search size={16} /><span>Explore the data</span></div>
          <label>
            <span>Category</span>
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option value="">All categories</option>
              {options.categories.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <label>
            <span>Price band</span>
            <select value={priceBand} onChange={(event) => setPriceBand(event.target.value)}>
              <option value="">All price bands</option>
              {options.price_bands.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
          <span className="filter-note"><CircleHelp size={14} /> Live warehouse query</span>
        </section>

        {error && <div className="error-banner" role="alert">{error}. Start PostgreSQL and load the Gold tables to restore live analytics.</div>}

        <section className="metric-grid" aria-label="Review summary">
          <article className="metric metric-primary">
            <div className="metric-top"><span>Reviews analyzed</span><MessageSquareText size={18} /></div>
            <strong>{loading ? '...' : formatNumber(summary?.reviews)}</strong>
            <small>After quality filtering</small>
          </article>
          <article className="metric">
            <div className="metric-top"><span>Average rating</span><Star size={18} /></div>
            <strong>{loading ? '...' : `${summary?.average_rating?.toFixed(2) || '0.00'}<i> / 5</i>`}</strong>
            <small>Across selected reviews</small>
          </article>
          <article className="metric">
            <div className="metric-top"><span>Positive sentiment</span><ArrowUpRight size={18} /></div>
            <strong>{loading ? '...' : `${positiveShare.toFixed(1)}<i>%</i>`}</strong>
            <small>Inferred from star ratings</small>
          </article>
          <article className="metric">
            <div className="metric-top"><span>Average price</span><Activity size={18} /></div>
            <strong>{loading ? '...' : `₹${formatNumber(summary?.average_price)}`}</strong>
            <small>Across selected reviews</small>
          </article>
        </section>

        <section className="analysis-grid">
          <article className="panel sentiment-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">01 / CUSTOMER MOOD</p><h2>Sentiment mix</h2></div>
              <span className="panel-tag">RATING-BASED LABELS</span>
            </div>
            <div className="sentiment-content">
              <div className="donut-wrap">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sentimentData} dataKey="value" nameKey="name" innerRadius="68%" outerRadius="92%" paddingAngle={3} stroke="none">
                      {sentimentData.map((entry) => <Cell key={entry.name} fill={SENTIMENT_COLORS[entry.name]} />)}
                    </Pie>
                    <Tooltip formatter={(value) => formatNumber(value)} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center"><strong>{loading ? '...' : `${positiveShare.toFixed(0)}%`}</strong><span>positive</span></div>
              </div>
              <div className="legend-list">
                {sentimentData.map((item) => {
                  const share = summary?.reviews ? (item.value / summary.reviews) * 100 : 0
                  return <div className="legend-row" key={item.name}>
                    <span className="legend-swatch" style={{ background: SENTIMENT_COLORS[item.name] }} />
                    <span className="legend-name">{item.name}</span>
                    <strong>{share.toFixed(1)}%</strong>
                    <small>{formatNumber(item.value)}</small>
                  </div>
                })}
                <p className="chart-note">Sentiment is derived from the product rating: 4–5 positive, 3 neutral, 1–2 negative.</p>
              </div>
            </div>
          </article>

          <article className="panel product-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">02 / PRODUCT SIGNAL</p><h2>Most reviewed</h2></div>
              <span className="panel-tag">TOP 12</span>
            </div>
            <div className="chart-area">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={products.slice(0, 8)} layout="vertical" margin={{ top: 2, right: 18, left: 8, bottom: 2 }}>
                  <XAxis type="number" hide />
                  <YAxis type="category" dataKey="product_name" width={132} tickLine={false} axisLine={false} tick={{ fill: '#53645a', fontSize: 11 }} />
                  <Tooltip formatter={(value) => [formatNumber(value), 'reviews']} cursor={{ fill: '#edf1e9' }} />
                  <Bar dataKey="reviews" fill="#427e64" radius={[0, 3, 3, 0]} barSize={15} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>
        </section>

        <section className="lower-grid">
          <article className="panel table-panel">
            <div className="panel-heading table-heading">
              <div><p className="eyebrow">03 / PRODUCT DETAIL</p><h2>Review leaders</h2></div>
              <span className="panel-tag">MINIMUM 100 REVIEWS</span>
            </div>
            <div className="table-scroll">
              <table>
                <thead><tr><th>Product</th><th>Category</th><th>Reviews</th><th>Rating</th><th>Positive</th></tr></thead>
                <tbody>
                  {products.slice(0, 8).map((product) => <tr key={product.product_name}>
                    <td className="product-name">{product.product_name}</td>
                    <td><span className="category-label">{product.category}</span></td>
                    <td>{formatNumber(product.reviews)}</td>
                    <td><span className="rating-value"><Star size={13} fill="currentColor" /> {Number(product.average_rating).toFixed(2)}</span></td>
                    <td><span className="positive-value"><ArrowUpRight size={14} /> {Number(product.positive_percent).toFixed(1)}%</span></td>
                  </tr>)}
                </tbody>
              </table>
              {!products.length && !loading && <div className="empty-state">No products found for these filters.</div>}
            </div>
          </article>

          <article className="panel predictor-panel">
            <div className="panel-heading">
              <div><p className="eyebrow">04 / MODEL LAB</p><h2>Test a review</h2></div>
              <span className="model-chip"><Sparkles size={13} /> MLlib</span>
            </div>
            <p className="predictor-copy">TF-IDF + Logistic Regression trained on review text.</p>
            <form onSubmit={submitReview}>
              <label className="visually-hidden" htmlFor="review-text">Review text</label>
              <textarea id="review-text" value={review} onChange={(event) => setReview(event.target.value)} maxLength={10000} required />
              <button type="submit" disabled={predicting || !review.trim()}>
                {predicting ? <LoaderCircle className="spin" size={16} /> : <Sparkles size={16} />}
                Analyze sentiment
              </button>
            </form>
            {prediction && (prediction.error
              ? <p className="prediction-error" role="alert">{prediction.error}</p>
              : <div className="prediction-result" aria-live="polite">
                  <div className="prediction-label"><span style={{ background: SENTIMENT_COLORS[prediction.sentiment] }} />
                    <small>PREDICTED SENTIMENT</small><strong>{prediction.sentiment}</strong></div>
                  <div className="probability-list">
                    {Object.entries(prediction.probabilities).map(([name, value]) => <div className="probability-row" key={name}>
                      <span>{name}</span><div><i style={{ width: `${value * 100}%`, background: SENTIMENT_COLORS[name] }} /></div><b>{(value * 100).toFixed(0)}%</b>
                    </div>)}
                  </div>
                </div>)}
            <div className="model-footnote"><ArrowDownRight size={14} /> Model target is derived from star ratings, not manually labeled opinions.</div>
          </article>
        </section>

        <footer className="page-footer">
          <span>PYSPARK · SPARK SQL · SPARK MLLIB · POSTGRESQL</span>
          <span>Data: Flipkart product reviews <span className="footer-separator">/</span> {loading ? 'Refreshing' : `${negativeShare.toFixed(1)}% negative share`}</span>
        </footer>
      </main>
    </div>
  )
}

export default App