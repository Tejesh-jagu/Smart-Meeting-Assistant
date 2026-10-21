import re


def _normalize_sentence(value):
    return " ".join(value.split()).casefold()


def _source_sentences(transcript):
    return [
        match.group().strip()
        for match in re.finditer(r"[^.!?]+[.!?](?=\s|$)", transcript)
    ]


def _source_units(transcript):
    """Split transcript text into exact sentence or line-sized evidence units."""
    return [
        unit.strip()
        for unit in re.split(r"(?<=[.!?;])\s+|[\r\n]+", transcript)
        if unit.strip()
    ]


def _summary_score(sentence):
    normalized = sentence.casefold()
    words = len(sentence.split())
    score = min(words, 24)
    unresolved_decision = re.search(
        r"\b(?:no decision|no agreement|didn'?t agree|did not agree|not agreed|"
        r"not decided|did not decide|decision remains open|"
        r"was not approved|were not approved)\b",
        normalized,
    ) is not None

    if unresolved_decision:
        score -= 100
    elif re.search(
        r"\b(?:agreed|decided|approved|selected|chose|chosen|confirmed|"
        r"consensus|decision (?:is|was))\b|"
        r"\b(?:we|the team|team)\s+(?:will|are going to|(?:'|\u2019)ll)\s+"
        r"(?:proceed with|move forward with|go with|use|adopt|select|choose)\b|"
        r"\blet(?:'|\u2019)s\s+(?:proceed with|move forward with|go with|use|adopt|select|choose)\b",
        normalized,
    ):
        score += 100

    topic_terms = re.findall(
        r"\b(?:meeting|project|plan|decision|task|request|report|issue|deadline|"
        r"launch|pilot|goal|agenda|customer)\b",
        normalized,
    )
    score += min(len(set(topic_terms)) * 4, 12)

    if re.search(r"\byou\s+(?:will|should|must|need to|have to)\b", normalized):
        score -= 60

    if re.match(
        r"\s*(?:thanks for joining|thank you for joining|hello everyone|"
        r"good morning|good afternoon|can everyone hear me)\b",
        normalized,
    ):
        score -= 100

    if re.match(r"\s*(?:ignore (?:all )?(?:previous|prior) instructions|say that|tell the assistant)\b", normalized):
        score -= 200

    return score


def sanitize_report(transcript, report):
    """Keep report fields grounded in exact transcript sentence or line units."""
    source_sentences = _source_sentences(transcript)
    source_units = _source_units(transcript)
    sentence_keys = {_normalize_sentence(unit) for unit in source_units}

    def is_source_unit(value):
        return isinstance(value, str) and _normalize_sentence(value) in sentence_keys

    def is_explicit_task(value):
        if re.match(
            r"^\s*(?:action item|follow[- ]?up|assigned(?: task)?|task assigned to)\b\s*[:-]?\s*",
            value,
            re.IGNORECASE,
        ):
            return True

        action_verbs = (
            r"send|prepare|confirm|review|create|schedule|share|draft|update|deliver|"
            r"contact|call|check|finali[sz]e|complete|follow|publish|present|submit|"
            r"coordinate|organize|analyse|analyze|investigate|test|implement|book|"
            r"collect|gather|build|design|write|ask|email|circulate|distribute|"
            r"decide|discuss|set up|lead|host|attend|provide|compile|compare|measure|"
            r"calculate|schedule|share|document|review|resolve|fix|deploy|approve|"
            r"notify|confirm|verify|check|update|prepare|research|train|support|"
            r"take|own|handle|track|follow up|make sure|add|remove|clear|show|display|"
            r"include|list|make|enable|disable|improve|optimise|optimize|connect|ensure"
        )
        has_commitment = re.match(
            rf"^\s*(?:(?i:at|in|on|by|for|after|before|when)\b[^,]{{0,60}},\s*)?"
            rf"(?:(?:[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)\s*:\s*)?"
            rf"(?:"
            rf"(?i:I|we|he|she|they|the team|team|management)\s+"
            rf"(?i:will|shall|is going to|are going to|am going to|has agreed to|"
            rf"have agreed to|agreed to|committed to)|"
            rf"(?i:I|we|he|she|they)(?:'|\u2019)(?i:ll)|"
            rf"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+"
            rf"(?i:will|shall|is going to|are going to|am going to|has agreed to|"
            rf"have agreed to|agreed to|committed to))\s+"
            rf"(?:{action_verbs})\b",
            value,
        )
        is_direct_request = re.match(
            rf"^\s*(?:(?i:please|kindly|and|then)\s+)*(?:{action_verbs})\b",
            value,
            re.IGNORECASE,
        )
        is_assigned_request = re.match(
            rf"^\s*(?:(?i:can|could|would)\s+you\s+)(?:{action_verbs})\b",
            value,
            re.IGNORECASE,
        )
        is_requirement = re.search(
            r"\b(?:should|must|needs? to|has to|have to|need to)\s+"
            r"(?:be\s+)?(?:added|included|listed|shown|displayed|appear|updated|"
            r"fixed|removed|created|saved|connected|provided|reviewed|completed)\b",
            value,
            re.IGNORECASE,
        )
        return bool(
            has_commitment or is_direct_request or is_assigned_request or is_requirement
        )

    def is_explicit_decision(value):
        unresolved = re.search(
            r"\b(?:no decision|no agreement|not agreed|did not agree|didn't agree|"
            r"have not agreed|has not agreed|not decided|did not decide|has not decided|"
            r"haven't decided|hasn't decided|decision remains open|decision is open|"
            r"decision is (?:still )?(?:open|pending|unresolved|not final)|"
            r"still undecided|undecided|pending approval|"
            r"was not approved|were not approved|not approved)\b",
            value,
            re.IGNORECASE,
        )
        instruction_like = re.match(
            r"^\s*(?:ignore (?:all )?(?:previous|prior) instructions|say that|"
            r"tell the assistant|pretend that)\b",
            value,
            re.IGNORECASE,
        )
        if unresolved or instruction_like:
            return False

        decision_verbs = (
            r"agreed|decided|approved|selected|chose|confirmed|voted|picked|adopted|"
            r"accepted|rejected|declined|settled on|landed on|went with|opted for|ruled out"
        )
        decision_subject = (
            r"(?:(?i:we|I|the team|team|management|the participants|participants|"
            r"everyone|all of us)|[A-Z][A-Za-z'-]+(?:\s+[A-Z][A-Za-z'-]+)?)"
        )
        if re.search(
            rf"\b{decision_subject}\s+(?:(?i:have|has|had)\s+|(?:'|\u2019)(?i:ve)\s+)?"
            rf"(?:{decision_verbs})\b",
            value,
        ):
            return True

        decision_outcomes = (
            r"use|adopt|select|selected|choose|chose|approve|approved|confirm|confirmed|"
            r"launch|set|schedule|keep|drop|move forward with|proceed(?: with)?|go with|"
            r"delay|defer|postpone|cancel|continue|stop|switch to|move to"
        )
        explicit_patterns = (
            rf"^\s*(?:the )?decision\s*:\s*"
            r"(?!no\b|not\b|pending\b|open\b|unresolved\b|tbd\b|unknown\b|unclear\b|undecided\b)\S+",
            rf"^\s*(?:the )?decision\s+(?:is|was)\s+(?:to\s+)?(?:{decision_outcomes})\b",
            r"^\s*(?:the )?decision\s+(?:is|was)\s+(?:the |an? )?"
            r"(?:option|choice|vendor|plan|date|platform|design|approach|timeline|"
            r"budget|release|launch|candidate|version|strategy)\b",
            rf"\b(?:we|the team|team)\s+(?:will|are going to)\s+"
            rf"(?:proceed(?: with)?|move forward with|go with|use|adopt|select|choose|"
            rf"launch|delay|defer|postpone|cancel|continue|stop|switch to|move to)\b",
            r"\b(?:we(?:'|\u2019)re going with|we are going with|we went with)\b",
            rf"\bwe(?:'|\u2019)ll\s+(?:proceed(?: with)?|move forward with|go with|use|"
            rf"adopt|select|choose|launch|delay|defer|postpone|cancel|continue|stop|switch to|move to)\b",
            rf"\blet(?:'|\u2019)s\s+(?:proceed with|move forward with|go with|use|"
            rf"adopt|select|choose|launch|delay|cancel|continue|stop|switch to|move to)\b",
            r"\b(?:there was|we reached|the team reached)\s+(?:a )?consensus\b",
            r"^\s*(?:the )?(?:option|proposal|plan|date|vendor|platform|design|"
            r"approach|timeline|budget|release|launch|candidate|version|strategy)"
            r"(?:\s+[A-Za-z0-9'-]+){0,3}\s+"
            r"(?:was|has been|is)\s+(?:approved|selected|chosen|confirmed|adopted|"
            r"accepted|rejected|declined)\b",
        )
        return any(re.search(pattern, value, re.IGNORECASE) for pattern in explicit_patterns)

    def string_list(value):
        return value if isinstance(value, list) else []

    summary = max(source_sentences, key=_summary_score, default="")

    generated_tasks = [
        item for item in string_list(report.get("tasks", []))
        if is_source_unit(item) and is_explicit_task(item)
    ]
    # Recover explicit commitments and direct requests the model omitted from exact transcript text.
    committed_source_sentences = [
        unit for unit in source_units
        if is_explicit_task(unit)
    ]
    tasks = list(dict.fromkeys(generated_tasks + committed_source_sentences))

    generated_decisions = [
        item for item in string_list(report.get("decisions", []))
        if is_source_unit(item) and is_explicit_decision(item)
    ]
    # Keep clear decisions even when the model leaves them out of its response.
    source_decisions = [
        unit for unit in source_units
        if is_explicit_decision(unit)
    ]
    decisions = list(dict.fromkeys(generated_decisions + source_decisions))

    return {
        "summary": summary,
        "decisions": decisions,
        "tasks": tasks,
    }
