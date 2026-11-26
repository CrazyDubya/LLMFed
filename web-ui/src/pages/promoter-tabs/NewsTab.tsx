import type { WorldNewsArticle } from '../../api/client';

type BodyBlock = { kind: 'list'; items: string[] } | { kind: 'paragraph'; text: string };

function splitArticleBody(body: string): BodyBlock[] {
  const blocks: BodyBlock[] = [];
  for (const block of body.trim().split(/\r?\n\s*\r?\n/)) {
    if (!block) continue;
    const lines = block.split(/\r?\n/).map(line => line.trim());
    if (lines.every(line => line.startsWith('- '))) {
      const items = lines.map(line => line.slice(2));
      const previous = blocks.at(-1);
      if (previous?.kind === 'list') previous.items.push(...items);
      else blocks.push({ kind: 'list', items });
    } else {
      blocks.push({ kind: 'paragraph', text: lines.join(' ') });
    }
  }
  return blocks;
}

export default function NewsTab({ news }: { news: WorldNewsArticle[] | 'error' | null }) {
  const status = news === null ? 'Loading world news…'
    : news === 'error' ? 'World news is unavailable right now.'
    : news.length === 0 ? 'No articles yet. Advance time to see what makes the headlines.'
    : null;

  return (
    <section aria-labelledby="world-news-heading">
      <header className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="world-news-heading" className="text-xl font-bold text-white">World News</h2>
          <p className="mt-1 text-sm text-gray-400">Results, reports, and stories from around the wrestling world.</p>
        </div>
        {Array.isArray(news) && news.length > 0 && (
          <span className="text-xs text-gray-400">{news.length} {news.length === 1 ? 'article' : 'articles'}</span>
        )}
      </header>

      {status && (
        <p role="status" className="rounded-lg border border-gray-800 bg-[#1a1a24] px-4 py-8 text-center text-sm text-gray-400">
          {status}
        </p>
      )}

      <div className="space-y-3">
        {Array.isArray(news) && news.map(article => (
          <article key={article.id} className="rounded-lg border border-gray-800 bg-[#1a1a24] p-4 sm:px-6">
            <header className="mb-3">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${article.is_kayfabe
                  ? 'bg-amber-900/50 text-amber-300'
                  : 'bg-purple-900/50 text-purple-300'}`}>
                  {article.category.replaceAll('_', ' ')}
                </span>
                <time dateTime={article.game_date} className="text-xs tabular-nums text-gray-400">{article.game_date}</time>
              </div>
              <h3 className="text-lg font-semibold leading-snug text-white">{article.headline}</h3>
              <p className="mt-1 text-xs text-gray-400">{article.source}</p>
            </header>
            <div className="max-w-prose space-y-3 text-sm leading-relaxed text-gray-300">
              {splitArticleBody(article.body).map((block, index) => block.kind === 'list' ? (
                <ul key={index} className="list-disc space-y-1 pl-5 marker:text-gray-500">
                  {block.items.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}
                </ul>
              ) : (
                <p key={index}>{block.text}</p>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
