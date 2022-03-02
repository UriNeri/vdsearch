import logging
from pathlib import Path
from turtle import title
import rich
from rich.console import Console

import typer
from vdsearch.commands.ribozyme_filter import ribozyme_filter
from vdsearch.commands.canonicalize import canonicalize

from vdsearch.types import FASTA, ReferenceCms, Threads
from vdsearch.utils import check_executable_exists
from . import (
    download_cms,
    download_viroiddb,
    find_circs,
    dedup,
    write_seqs,
    cluster,
    infernal,
)
from vdsearch.nim import write_seqs as ws


def easy_search(
    fasta: Path = FASTA,
    reference_db: Path = typer.Option(
        None,
        help="Path to FASTA-formatted reference viroid database. If none is provided, the latest ViroidDB will be used.",
        file_okay=True,
        dir_okay=False,
    ),
    reference_cms: Path = ReferenceCms,
    threads: int = Threads,
):
    """
    Search for viroid-like sequences.


    ## Pipeline description

    At a high level, this workflow follows these steps:

    1. Find circRNAs
    2. For each circRNA compute a canonical representation
    3. Deduplicate the circRNAs
    4. Search them for ribozymes
    5. Also search the circRNAs against a database of known viroid-like RNAs (ViroidDB)
    6. Using the ribozyme data and search results, output viroid-like sequences
    """

    # preflight checks
    logging.debug("Checking that all needed tools exist...")
    check_executable_exists("seqkit")
    check_executable_exists("cmsearch")
    check_executable_exists("mmseqs")
    logging.debug("All needed tools exist.")

    logging.info(f"Beginning search for viroid-like RNAs using {threads} threads...")
    # if not reference_db:
    #     download.download_viroiddb()

    # if not reference_cms:
    #     download.download_cms()

    # run cirit/rotcanon
    circs = Path(f"01.{fasta.stem}.circs.fasta")
    find_circs(fasta, circs, canonicalize=True)

    # run dedup using seqkit
    deduped_circs = Path(f"03.{fasta.stem}.deduped.fasta")
    dedup(circs, deduped_circs, threads=threads)

    # run infernal
    cmsearch_output = Path(f"04.{fasta.stem}.infernal.out")
    cmsearch_tsv = Path(f"04.{fasta.stem}.infernal.tsv")
    infernal(
        deduped_circs,
        output=cmsearch_output,
        output_tsv=cmsearch_tsv,
        reference_cms=reference_cms,
        threads=threads,
        cmscan=False,
    )

    # find the viroids in the infernal output
    ribozymes = ribozyme_filter(cmsearch_tsv, cm_file=reference_cms)
    rz_seqs = Path(f"05.{fasta.stem}.ribozymes.fasta")
    logging.info("Outputting viroid-like sequences...")
    ws.write_seqs(
        str(deduped_circs),
        str(rz_seqs),
        ribozymes["ribozy_likes"].seq_id.tolist(),
    )
    logging.done(f"Wrote to {rz_seqs}")  # type: ignore

    # # run mmseqs
    # mmseqs(fasta)

    # remove_rz_only_hits(fasta)

    # logging.done(f"The results are in [green bold]{fasta.stem}_viroidlikes.fasta.[/]")  # type: ignore
    Console().log(
        # "\n",
        # "Thanks for using [green]vdsearch[/]!",
        "\n",
        rich.panel.Panel(
            rich.markdown.Markdown(
                """
If you use these results in your research, please cite:

> B.D. Lee *et al.* (2022) vdsearch: A tool for viroid-like RNA searches.
            """
            ),
            title_align="left",
            border_style="dim",
            width=88,
            title="Citation",
        ),
        "\n",
        "[dim]Brought to you by: [cyan bold]NIH/NLM/NCBI[/], [blue bold]University of Oxford[/], and [bold]Tel Aviv University[/][/dim]",
        "\n",
    )
