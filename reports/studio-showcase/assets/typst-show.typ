#show: doc => studio(
$if(title)$
  title: [$title$],
$endif$
$if(subtitle)$
  subtitle: [$subtitle$],
$endif$
$if(by-author)$
  authors: (
$for(by-author)$
$if(it.name.literal)$
    ( name: [$it.name.literal$] ),
$endif$
$endfor$
  ),
$endif$
$if(date)$
  date: [$date$],
$endif$
$if(abstract)$
  abstract: [$abstract$],
$endif$
$if(organization)$
  organization: [$organization$],
$endif$
$if(eyebrow)$
  eyebrow: [$eyebrow$],
$endif$
$if(title-layout)$
  title-layout: "$title-layout$",
$endif$
$if(accent-typst)$
  accent: "#$accent-typst$",
$endif$
$if(confidential-mark)$
  confidential-mark: [$confidential-mark$],
$endif$
$if(metrics)$
  metrics: (
$for(metrics)$
    ( value: [$it.value$], label: [$it.label$] ),
$endfor$
  ),
$endif$
$if(papersize)$
  paper: "$papersize$",
$endif$
$if(mainfont)$
  font: ("$mainfont$",),
$endif$
$if(fontsize)$
  fontsize: $fontsize$,
$endif$
$if(section-numbering)$
  sectionnumbering: "$section-numbering$",
$endif$
  pagenumbering: $if(page-numbering)$"$page-numbering$"$else$none$endif$,
  doc,
)
