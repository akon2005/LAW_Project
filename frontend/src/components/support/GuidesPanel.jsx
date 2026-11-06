import { useCallback, useEffect, useState } from 'react'
import Icon from '../Icon.jsx'
import { supportApi } from '../../services/supportApi.js'
import { describeError, exampleBadge, groupExamples } from '../../utils/supportChat.js'
import './support.css'

/**
 * Guides: the on-site half of demo mode.
 *
 * The gallery, the capability registry, the troubleshooting index and the
 * support articles all come from the live support backend — the same data the
 * assistant uses — so an example can never mean one thing here and something
 * else in the chat. Cards that run a real capability say so; illustrative
 * examples are labelled and never presented as legal output.
 */
function Badge({ children, tone = 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

const STATUS_TONE = {
  implemented: 'green',
  partial: 'gold',
  experimental: 'gold',
  planned: 'neutral',
  not_available: 'neutral',
}

export default function GuidesPanel({ onLoadPrompt, demoMode = false }) {
  const [examples, setExamples] = useState(null)
  const [examplesError, setExamplesError] = useState('')
  const [features, setFeatures] = useState(null)
  const [featuresError, setFeaturesError] = useState('')
  const [articles, setArticles] = useState(null)
  const [articlesError, setArticlesError] = useState('')
  const [openArticle, setOpenArticle] = useState(null)
  const [activeCategory, setActiveCategory] = useState('')

  const load = useCallback(async () => {
    setExamplesError('')
    setFeaturesError('')
    setArticlesError('')
    try {
      setExamples(await supportApi.examples())
    } catch (err) {
      setExamplesError(describeError(err?.status ?? 0, err?.payload).message)
    }
    try {
      setFeatures(await supportApi.features())
    } catch (err) {
      setFeaturesError(describeError(err?.status ?? 0, err?.payload).message)
    }
    try {
      setArticles(await supportApi.articles({ limit: 100 }))
    } catch (err) {
      setArticlesError(describeError(err?.status ?? 0, err?.payload).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const groups = exampleBadge ? groupExamples(examples?.examples || [], examples?.categories || []) : []
  const shownGroups = activeCategory ? groups.filter((group) => group.id === activeCategory) : groups

  const openArticleBody = async (articleId) => {
    if (openArticle?.id === articleId) {
      setOpenArticle(null)
      return
    }
    try {
      const detail = await supportApi.article(articleId)
      setOpenArticle(detail)
    } catch (err) {
      setOpenArticle({ id: articleId, title: 'Unavailable', body: describeError(err?.status ?? 0, err?.payload).message })
    }
  }

  return (
    <section className="page-section section-container guides-page">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Guide &amp; demonstration mode</span>
          <h2>Examples, feature status and support articles</h2>
        </div>
        <p>
          Every item below is served by the support backend, so the gallery in the assistant and the
          gallery here are the same data. Examples are labelled <strong>verified project data</strong> or an{' '}
          <strong>illustrative teaching example</strong>, and nothing stages a fake search or prediction.
          {demoMode ? ' Demo mode is on.' : ''}
        </p>
      </div>

      {examplesError && (
        <div className="empty-card"><h3>Example gallery unavailable</h3><p>{examplesError}</p></div>
      )}

      {examples && (
        <>
          <div className="guides-toolbar">
            <button type="button" className={`okf-chip ${activeCategory === '' ? 'active' : ''}`} onClick={() => setActiveCategory('')}>
              All categories ({groups.reduce((total, group) => total + group.examples.length, 0)})
            </button>
            {groups.map((group) => (
              <button
                key={group.id}
                type="button"
                className={`okf-chip ${activeCategory === group.id ? 'active' : ''}`}
                onClick={() => setActiveCategory(group.id)}
              >
                {group.letter ? `${group.letter} · ` : ''}{group.label}
              </button>
            ))}
          </div>

          {shownGroups.length === 0 && (
            <div className="empty-card"><h3>No examples in this category</h3><p>Pick another category to see its prompts.</p></div>
          )}

          {shownGroups.map((group) => (
            <div className="guides-group" key={group.id}>
              <h3 className="guides-group-title">{group.letter ? `${group.letter} · ` : ''}{group.label}</h3>
              <div className="guides-grid">
                {group.examples.map((example) => {
                  const badge = exampleBadge(example)
                  return (
                    <article className="guides-card" key={example.id}>
                      <div className="guides-card-top">
                        <h4>{example.title}</h4>
                        <Badge tone={badge.tone}>{badge.label}</Badge>
                      </div>
                      <p className="guides-prompt">“{example.prompt}”</p>
                      <div className="guides-block">
                        <span className="answer-label">Learning objective</span>
                        <p>{example.learning_objective}</p>
                      </div>
                      {example.expected?.length > 0 && (
                        <div className="guides-block">
                          <span className="answer-label">What you should see</span>
                          <ul className="guides-list">
                            {example.expected.map((item) => <li key={item}>{item}</li>)}
                          </ul>
                        </div>
                      )}
                      <div className="guides-meta">
                        <span>{example.invokes_backend ? 'Runs a real backend capability' : 'Documentation only'}</span>
                        {example.expected_kind && <span>expected source: {example.expected_kind}</span>}
                      </div>
                      {example.illustrative_notice && <p className="guides-notice">{example.illustrative_notice}</p>}
                      {example.notes && <p className="guides-notice guides-notice--quiet">{example.notes}</p>}
                      <div className="guides-card-actions">
                        <button type="button" className="ghost-btn" onClick={() => onLoadPrompt?.(example.prompt, 'load')}>
                          Load into chat
                        </button>
                        <button type="button" className="outline-btn" onClick={() => onLoadPrompt?.(example.prompt, 'send')}>
                          Try this example <Icon name="arrow" size={15} />
                        </button>
                      </div>
                    </article>
                  )
                })}
              </div>
            </div>
          ))}
          {examples.note && <p className="guides-footnote">{examples.note}</p>}
        </>
      )}

      <div className="section-heading guides-subheading">
        <div>
          <span className="eyebrow">Capability registry</span>
          <h2>What is implemented</h2>
        </div>
        <p>
          Status labels are literal. “Not available” means the project reports the gap instead of
          producing an unvalidated result, and “experimental” flags a capability that is not validated.
        </p>
      </div>

      {featuresError && <div className="empty-card"><h3>Capability registry unavailable</h3><p>{featuresError}</p></div>}

      {features && (
        <>
          <div className="guides-status-row">
            {Object.entries(features.counts || {}).map(([status, count]) => (
              <span className="guides-status-count" key={status}>
                <Badge tone={STATUS_TONE[status] || 'neutral'}>{status.replace('_', ' ')}</Badge>
                <strong>{count}</strong>
              </span>
            ))}
            <span className="guides-status-note">
              {features.live_status_included ? 'Live status included for the outcome model' : 'Static registry only'}
            </span>
          </div>

          <div className="guides-table-wrap">
            <table className="okf-table guides-table">
              <thead>
                <tr><th>Feature</th><th>Status</th><th>Summary</th><th>Endpoint</th></tr>
              </thead>
              <tbody>
                {features.features.map((feature) => (
                  <tr key={feature.id}>
                    <td><strong>{feature.name}</strong></td>
                    <td><Badge tone={STATUS_TONE[feature.status] || 'neutral'}>{feature.status.replace('_', ' ')}</Badge></td>
                    <td>
                      {feature.summary}
                      {feature.recorded_metrics && (
                        <span className="guides-metrics">
                          recorded: accuracy {feature.recorded_metrics.test_accuracy} · macro F1 {feature.recorded_metrics.macro_f1} · test n={feature.recorded_metrics.test_size}
                        </span>
                      )}
                      {feature.notes && <span className="guides-metrics">{feature.notes}</span>}
                    </td>
                    <td>{feature.endpoint ? <code>{feature.endpoint}</code> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      <div className="section-heading guides-subheading">
        <div>
          <span className="eyebrow">Support articles</span>
          <h2>Guides and troubleshooting</h2>
        </div>
        <p>
          The same articles the assistant grounds its answers in. Troubleshooting entries carry
          meaning, likely causes, steps, retry advice and an escalation note.
        </p>
      </div>

      {articlesError && <div className="empty-card"><h3>Support articles unavailable</h3><p>{articlesError}</p></div>}

      {articles && (
        <div className="guides-articles">
          {articles.articles.map((article) => (
            <article className="guides-article" key={article.id}>
              <button type="button" className="guides-article-head" onClick={() => openArticleBody(article.id)}>
                <span>
                  <strong>{article.title}</strong>
                  <small>{article.category} · updated {article.updated}</small>
                </span>
                <Icon name={openArticle?.id === article.id ? 'chevron' : 'arrow'} size={16} />
              </button>
              <p className="guides-article-excerpt">{article.excerpt}</p>
              {openArticle?.id === article.id && (
                <pre className="guides-article-body">{openArticle.body}</pre>
              )}
            </article>
          ))}
        </div>
      )}

      {features?.known_problems?.length > 0 && (
        <div className="guides-problems">
          <span className="answer-label">Recognised problems</span>
          <div className="guides-problem-chips">
            {features.known_problems.map((problem) => (
              <button
                key={problem.id}
                type="button"
                className="assistant-chip"
                onClick={() => onLoadPrompt?.(`${problem.title}. What should I do?`, 'send')}
              >
                {problem.title}
              </button>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
