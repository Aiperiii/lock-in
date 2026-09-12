import json, uuid, random
random.seed(7)
def uid(): return str(uuid.uuid4())

def mcq(prompt, options, correct, expl, tag, diff="medium", source="ai"):
    return {"id": uid(), "type": "mcq", "prompt": prompt, "options": options,
            "correct_index": correct, "explanation": expl, "concept_tag": tag,
            "difficulty": diff, "source": source, "hint": None, "model_answer": None}

def openq(prompt, hint, model, expl, tag, diff="medium", source="ai"):
    return {"id": uid(), "type": "open", "prompt": prompt, "options": None,
            "correct_index": None, "explanation": expl, "concept_tag": tag,
            "difficulty": diff, "source": source, "hint": hint, "model_answer": model}

def lesson(num, title, mins, kind, tags, blocks):
    return {"id": uid(), "number": num, "title": title, "estimated_minutes": mins,
            "kind": kind, "concept_tags": tags, "blocks": blocks}

def prose(t): return {"kind": "prose", "content": t}
def q(qq): return {"kind": "question", "question": qq}

def build_blocks(items):
    out = []
    for i, it in enumerate(items):
        b = dict(it); b["id"] = uid(); b["order"] = i
        out.append(b)
    return out

# ---- Lesson 1.1
l11 = build_blocks([
 prose("An algorithm is a finite sequence of well-defined steps that transforms an input into an output. The emphasis on *finite* matters: a procedure that never terminates is not an algorithm, however useful its partial results might be."),
 prose("Every algorithm must also be unambiguous. Each step has to be precise enough that it could be carried out mechanically, without judgement calls from whoever is following it."),
 q(mcq("Which of the following disqualifies a procedure from being an algorithm?",
   ["It uses randomness", "It never terminates on some inputs", "It is slow", "It requires extra memory"],
   1, "Finiteness is part of the definition. Randomized and slow procedures are still algorithms; a non-terminating one is not.",
   "algorithm-definition", "easy", "book")),
 prose("We care about algorithms in the abstract, independent of the machine running them. This is why analysis focuses on how work grows with input size rather than on seconds elapsed on a particular laptop."),
 q(openq("In your own words, why is measuring an algorithm in seconds a poor way to compare two algorithms?",
   "Think about what changes when you run the same code on a faster machine.",
   "Wall-clock time depends on hardware, language, compiler and load. Growth rate is a property of the algorithm itself and predicts behaviour as input scales.",
   "Timing measures the environment as much as the algorithm; growth rate isolates the algorithm.",
   "why-asymptotic-analysis", "medium", "ai")),
])

# ---- Lesson 1.2
l12 = build_blocks([
 prose("The running time of an algorithm is usually expressed as a function of input size n. Rather than count exact operations, we ask how that count grows as n increases."),
 q(mcq("An algorithm performs 3n + 17 operations. What dominates as n grows large?",
   ["The constant 17", "The coefficient 3", "The term n", "Nothing dominates"],
   2, "As n grows, the linear term overwhelms the constant, and constant factors do not change the growth class.",
   "growth-rates", "easy", "ai")),
 prose("Growth rates form a hierarchy. Constant time is followed by logarithmic, then linear, then linearithmic, then polynomial, then exponential and factorial time."),
 prose("The gaps between these classes are enormous at scale. An O(n²) algorithm on a million elements does roughly a trillion operations; an O(n log n) algorithm does about twenty million."),
 q(mcq("Which ordering is correct from slowest-growing to fastest-growing?",
   ["O(log n), O(1), O(n), O(n²)", "O(1), O(log n), O(n log n), O(n²)", "O(1), O(n), O(log n), O(n²)", "O(n), O(1), O(log n), O(2ⁿ)"],
   1, "Constant, then logarithmic, then linear, then linearithmic, then polynomial.",
   "growth-hierarchy", "medium", "book")),
])

# ---- Lesson 1.3
l13 = build_blocks([
 prose("An algorithm's time complexity describes how its runtime grows as input size n increases. Big-O notation captures the worst-case upper bound, discarding constants and lower-order terms — O(3n² + 2n + 7) simplifies to O(n²)."),
 prose("The hierarchy from fastest to slowest growth: O(1) → O(log n) → O(n) → O(n log n) → O(n²) → O(2ⁿ) → O(n!). Binary search achieves O(log n) because each step halves the search space — one million elements need at most ~20 comparisons."),
 q(mcq("A nested loop where the outer runs n times and the inner also runs n times has what time complexity?",
   ["O(n)", "O(n log n)", "O(n²)", "O(2ⁿ)"],
   2, "Each of the n outer iterations triggers n inner iterations, giving n × n total work.",
   "nested-loop-complexity", "easy", "book")),
 q(openq("In your own words, explain why O(log n) algorithms scale so dramatically better than O(n) for large inputs. Give one concrete example.",
   "Consider how binary search handles 10⁶ vs 10⁹ elements — how many more steps does it need?",
   "Logarithmic growth adds a constant number of steps each time input multiplies. Going from a million to a billion elements adds only about ten comparisons to a binary search, while a linear scan does a thousand times more work.",
   "Multiplying the input size adds only a constant to a logarithmic cost, but multiplies a linear cost.",
   "logarithmic-scaling", "medium", "ai")),
 q(mcq("Which correctly simplifies O(5n³ + 12n² + 100)?",
   ["O(5n³)", "O(n³ + n²)", "O(n³)", "O(n²)"],
   2, "Constant factors and lower-order terms are dropped, leaving the dominant term.",
   "simplifying-big-o", "easy", "book")),
 prose("Space complexity follows the same notation. Recursive algorithms consume O(depth) call stack frames. A function that recurses n levels deep without tail-call optimization uses O(n) stack space — even if it does no explicit allocation."),
 prose("Amortized analysis averages cost across a sequence of operations. A dynamic array doubles capacity when full — one O(n) resize — but this is rare. Summing all n appends, total cost is O(n), so each append is O(1) amortized."),
 q(openq("Why doesn't the occasional O(n) resize contradict the claim that dynamic array append is O(1) amortized?",
   "How often does a resize happen relative to the total number of appends that precede it?",
   "Resizes happen at exponentially spaced intervals, so their total cost across n appends is O(n). Spread over n operations that averages to constant time each.",
   "The expensive operations are rare enough that their total cost is linear across all appends.",
   "amortized-analysis", "hard", "book")),
])

l14 = build_blocks([
 prose("Practice applying complexity analysis to code you have not seen before. For each snippet, identify the dominant operation and count how many times it runs."),
 q(mcq("A loop that halves n each iteration until n reaches 1 runs how many times?",
   ["n times", "n/2 times", "log₂ n times", "√n times"],
   2, "Each iteration halves the remaining size, so the count is the number of halvings needed, which is log₂ n.",
   "loop-analysis", "medium", "ai")),
 q(mcq("Two sequential loops, each running n times, give what total complexity?",
   ["O(n²)", "O(2n) = O(n)", "O(n log n)", "O(log n)"],
   1, "Sequential work adds rather than multiplies, and constant factors drop.",
   "sequential-vs-nested", "easy", "book")),
])

ch1 = {"id": uid(), "number": 1, "title": "Complexity & Big-O",
       "summary": "How to measure algorithm cost independently of hardware.",
       "lessons": [
         lesson(1, "What Is an Algorithm?", 8, "reading", ["algorithm-definition","why-asymptotic-analysis"], l11),
         lesson(2, "Growth of Functions", 14, "reading", ["growth-rates","growth-hierarchy"], l12),
         lesson(3, "Big-O, Θ, and Ω Notation", 18, "reading", ["nested-loop-complexity","logarithmic-scaling","simplifying-big-o","amortized-analysis"], l13),
         lesson(4, "Practice: Analyze the Complexity", 12, "practice", ["loop-analysis","sequential-vs-nested"], l14),
       ]}

def stub_chapter(num, title, summary, lessons):
    return {"id": uid(), "number": num, "title": title, "summary": summary,
            "lessons": [lesson(i+1, t, m, "reading", [tag], build_blocks([
                prose(f"Placeholder prose for {t}. Real content comes from the uploaded PDF."),
                q(mcq(f"Sample question for {t}?", ["A","B","C","D"], 0,
                      "Sample explanation.", tag, "medium", "ai")),
            ])) for i,(t,m,tag) in enumerate(lessons)]}

ch2 = stub_chapter(2, "Sorting Algorithms", "Comparison sorts and their bounds",
  [("Insertion Sort",10,"insertion-sort"),("Merge Sort",16,"merge-sort"),
   ("Quicksort",18,"quicksort"),("Lower Bounds for Sorting",12,"sorting-lower-bound")])
ch3 = stub_chapter(3, "Data Structures", "Structures that make operations cheap",
  [("Stacks and Queues",9,"stacks-queues"),("Hash Tables",15,"hash-tables"),
   ("Binary Search Trees",17,"bst")])
ch4 = stub_chapter(4, "Graph Algorithms", "Traversal and shortest paths",
  [("Graph Representations",11,"graph-representation"),("BFS and DFS",16,"traversal"),
   ("Dijkstra's Algorithm",19,"dijkstra")])

course = {
  "id": uid(),
  "title": "Introduction to Algorithms",
  "author": "Cormen, Leiserson, Rivest & Stein",
  "cover_seed": 42,
  "status": "ready",
  "progress_percent": 11,
  "chapters": [ch1, ch2, ch3, ch4],
}

with open("/home/claude/lockedin/mock/course.json","w") as f:
    json.dump(course, f, indent=2, ensure_ascii=False)

total = sum(len(c["lessons"]) for c in course["chapters"])
qs = sum(1 for c in course["chapters"] for l in c["lessons"] for b in l["blocks"] if b["kind"]=="question")
print("chapters", len(course["chapters"]), "lessons", total, "questions", qs)
