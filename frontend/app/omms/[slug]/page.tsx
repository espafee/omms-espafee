import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { OmmsContentPage } from "../components/OmmsMarketing";
import { pages } from "../content";

type PageParams = {
  params: Promise<{
    slug: string;
  }>;
};

export function generateStaticParams() {
  return Object.keys(pages).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageParams): Promise<Metadata> {
  const { slug } = await params;
  const page = pages[slug];

  if (!page) {
    return {
      title: "OMMS | VistaAi",
    };
  }

  return {
    title: `${page.eyebrow} | OMMS by VistaAi`,
    description: page.intro,
  };
}

export default async function OmmsSubPage({ params }: PageParams) {
  const { slug } = await params;
  const page = pages[slug];

  if (!page) {
    notFound();
  }

  return <OmmsContentPage page={page} />;
}
